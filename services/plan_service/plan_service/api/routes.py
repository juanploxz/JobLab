"""Thin route handlers: parse input, call one use case, present its result."""

from __future__ import annotations

import json
from typing import Any

from flask import Blueprint, current_app, jsonify, request, url_for
from pydantic import BaseModel, ValidationError
from sqlalchemy import text

from plan_service import bootstrap
from plan_service.api import presenters
from plan_service.api.errors import InvalidRequest
from plan_service.api.inputs import CreateVacancyInput, GeneratePlanInput, field_errors
from plan_service.dtos import CreateVacancyCommand
from plan_service.extensions import db
from plan_service.i18n import _


def parse_body(schema: type[BaseModel]) -> BaseModel:
    raw = request.get_data(cache=True, as_text=True)
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        raise InvalidRequest("parse_error", _("El cuerpo JSON está mal formado.")) from exc
    if not isinstance(payload, dict):
        raise InvalidRequest("invalid_request", _("El cuerpo debe ser un objeto JSON."))
    try:
        return schema.model_validate(payload)
    except ValidationError as exc:
        raise InvalidRequest(
            "invalid_request",
            _("La solicitud contiene datos inválidos."),
            field_errors(exc),
        ) from exc


def _int_arg(name: str, default: int) -> int:
    try:
        return int(request.args.get(name, default))
    except (TypeError, ValueError):
        return default


def build_plans_blueprint(name: str) -> Blueprint:
    """The same contract is mounted on /api/v2 and on the strangled /api/v1 route."""
    blueprint = Blueprint(name, __name__)

    @blueprint.get("/plans/")
    def list_plans():
        max_size = current_app.config["MAX_PAGE_SIZE"]
        page_size = min(max(_int_arg("page_size", current_app.config["DEFAULT_PAGE_SIZE"]), 1), max_size)
        page = _int_arg("page", 1)
        result = bootstrap.list_plans_service().execute(page=page, page_size=page_size)

        def page_url(number: int) -> str:
            return url_for(f"{name}.list_plans", page=number, page_size=page_size, _external=True)

        return jsonify(
            {
                "count": result.total,
                "next": page_url(page + 1) if result.has_next else None,
                "previous": page_url(page - 1) if result.has_previous else None,
                "results": [presenters.plan_summary(item) for item in result.items],
            }
        )

    @blueprint.post("/plans/")
    def create_plan():
        data = parse_body(GeneratePlanInput)
        plan = bootstrap.generation_service().execute(data.company_description)
        detail = bootstrap.get_plan_service().execute(plan.id)
        response = jsonify(presenters.plan_detail(detail))
        response.status_code = 201
        response.headers["Location"] = url_for(f"{name}.get_plan", plan_id=detail.id, _external=True)
        return response

    @blueprint.get("/plans/<int:plan_id>/")
    def get_plan(plan_id: int):
        return jsonify(presenters.plan_detail(bootstrap.get_plan_service().execute(plan_id)))

    @blueprint.post("/plans/<int:plan_id>/vacancies/")
    def create_vacancy(plan_id: int):
        data: CreateVacancyInput = parse_body(CreateVacancyInput)
        command = CreateVacancyCommand(
            department_id=data.department_id,
            name=data.name,
            available_positions=data.available_positions,
            salary_min=data.salary_min,
            salary_max=data.salary_max,
            currency=data.currency,
            salary_period=data.salary_period,
            description=data.description,
            required_knowledge=tuple(data.required_knowledge),
            reports_to=data.reports_to or "",
        )
        result = bootstrap.create_vacancy_service().execute(plan_id, command)
        response = jsonify(presenters.vacancy(result))
        response.status_code = 201
        response.headers["Location"] = url_for(
            f"{name}.get_vacancy", plan_id=plan_id, vacancy_id=result.id, _external=True
        )
        return response

    @blueprint.get("/plans/<int:plan_id>/vacancies/<int:vacancy_id>/")
    def get_vacancy(plan_id: int, vacancy_id: int):
        return jsonify(presenters.vacancy(bootstrap.get_vacancy_service().execute(plan_id, vacancy_id)))

    return blueprint


public_blueprint = Blueprint("public", __name__)


@public_blueprint.get("/summary/")
def public_summary():
    limit = min(max(_int_arg("limit", 10), 1), 50)
    data = bootstrap.public_summary_service().execute(latest_limit=limit)
    return jsonify(
        {
            "system": "JobLab",
            "service": current_app.config["SERVICE_NAME"],
            "version": current_app.config["SERVICE_VERSION"],
            "description": _(
                "Resumen público de planes organizacionales y vacantes generadas en JobLab."
            ),
            **presenters.public_summary(data),
        }
    )


strangler_blueprint = Blueprint("strangler", __name__)


@strangler_blueprint.post("/organizational-plan/")
def preview_organizational_plan():
    """Taller 02 endpoint, now backed by the real domain instead of keyword rules."""
    data = parse_body(GeneratePlanInput)
    description, proposal = bootstrap.preview_service().execute(data.company_description)
    return jsonify(
        {
            "message": _("Plan organizacional generado por el microservicio estrangulador"),
            "source": "flask",
            "pattern": "strangler",
            "company_description": description,
            "proposal": proposal.model_dump(mode="json"),
        }
    )


ops_blueprint = Blueprint("ops", __name__)


@ops_blueprint.get("/")
def index() -> Any:
    return jsonify(
        {
            "service": current_app.config["SERVICE_NAME"],
            "version": current_app.config["SERVICE_VERSION"],
            "status": "ok",
            "pattern": "strangler",
            "routes": [
                "/health",
                "/api/v2/plans/",
                "/api/v2/plans/{id}/",
                "/api/v2/plans/{id}/vacancies/",
                "/api/v2/public/summary/",
                "/api/v2/organizational-plan/",
            ],
        }
    )


@ops_blueprint.get("/health")
def health() -> Any:
    try:
        db.session.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001 - reported as degraded health
        database = "unavailable"
    status = "ok" if database == "ok" else "degraded"
    response = jsonify(
        {
            "status": status,
            "service": current_app.config["SERVICE_NAME"],
            "version": current_app.config["SERVICE_VERSION"],
            "checks": {"database": database},
        }
    )
    response.status_code = 200 if status == "ok" else 503
    return response
