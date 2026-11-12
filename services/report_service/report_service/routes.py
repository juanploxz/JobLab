"""HTTP API of the report service: enqueue work (202 Accepted) and poll its status."""

from __future__ import annotations

import json
import logging
import re

from celery.result import AsyncResult
from flask import Blueprint, Flask, Response, current_app, jsonify, request, url_for
from werkzeug.exceptions import HTTPException

from report_service.celery_app import celery, settings
from report_service.i18n import _
from report_service.reports import ReportRendererFactory
from report_service.stores import get_store
from report_service.tasks import generate_plan_report

logger = logging.getLogger(__name__)
TASK_ID_PATTERN = re.compile(r"^[0-9a-f-]{32,36}$")

api = Blueprint("reports", __name__)


def _error(code: str, detail: str, status: int):
    return jsonify({"error": {"code": code, "detail": detail}}), status


def _store():
    return get_store(settings["NOTIFICATION_STORE_URL"], settings["MAX_NOTIFICATIONS"])


def _language() -> str:
    best = request.accept_languages.best_match(current_app.config["SUPPORTED_LOCALES"])
    return best or current_app.config["BABEL_DEFAULT_LOCALE"]


@api.post("/reports/")
def request_report():
    try:
        payload = json.loads(request.get_data(as_text=True) or "{}")
    except json.JSONDecodeError:
        return _error("parse_error", _("El cuerpo JSON está mal formado."), 400)
    plan_id = payload.get("plan_id") if isinstance(payload, dict) else None
    report_format = str((payload or {}).get("format", "csv")).lower() if isinstance(payload, dict) else ""
    if isinstance(plan_id, bool) or not isinstance(plan_id, int) or plan_id < 1:
        return _error("invalid_request", _("plan_id debe ser un entero positivo."), 400)
    if report_format not in ReportRendererFactory.formats():
        return _error(
            "invalid_request",
            _("format debe ser uno de: %(options)s.", options=", ".join(ReportRendererFactory.formats())),
            400,
        )

    try:
        result = generate_plan_report.apply_async(
            args=[plan_id, report_format, _language()],
            retry=True,
            retry_policy={"max_retries": 2, "interval_start": 0, "interval_step": 0.5, "interval_max": 1},
        )
        _store().register_report(
            result.id,
            {"plan_id": plan_id, "format": report_format},
            current_app.config["REPORT_RESULT_TTL_SECONDS"],
        )
    except Exception:  # noqa: BLE001 - broker or store unavailable
        logger.exception("Could not enqueue report")
        return _error("broker_unavailable", _("El servicio de colas no está disponible."), 503)

    response = jsonify(_status_payload(result.id, {"plan_id": plan_id, "format": report_format}))
    response.status_code = 202
    response.headers["Location"] = url_for("reports.report_status", task_id=result.id, _external=True)
    return response


def _status_payload(task_id: str, metadata: dict) -> dict:
    result = AsyncResult(task_id, app=celery)
    state = result.state
    payload = {
        "task_id": task_id,
        "plan_id": metadata.get("plan_id"),
        "format": metadata.get("format"),
        "status": state,
        "status_url": url_for("reports.report_status", task_id=task_id, _external=True),
        "download_url": None,
        "error": None,
    }
    if state == "SUCCESS":
        payload["download_url"] = url_for("reports.download_report", task_id=task_id, _external=True)
    elif state == "FAILURE":
        not_found = type(result.result).__name__ == "PlanNotFound"
        payload["error"] = {
            "code": "plan_not_found" if not_found else "report_failed",
            "detail": _("El plan solicitado no existe.") if not_found else _("No fue posible generar el reporte."),
        }
    return payload


def _known(task_id: str):
    if not TASK_ID_PATTERN.fullmatch(task_id):
        return None
    return _store().report(task_id)


@api.get("/reports/<task_id>/")
def report_status(task_id: str):
    metadata = _known(task_id)
    if metadata is None:
        return _error("report_not_found", _("No existe un reporte con ese identificador."), 404)
    return jsonify(_status_payload(task_id, metadata))


@api.get("/reports/<task_id>/download/")
def download_report(task_id: str):
    if _known(task_id) is None:
        return _error("report_not_found", _("No existe un reporte con ese identificador."), 404)
    result = AsyncResult(task_id, app=celery)
    if result.state != "SUCCESS":
        return _error("report_not_ready", _("El reporte todavía no está listo."), 409)
    document = result.result
    return Response(
        document["content"],
        mimetype=document["content_type"].split(";")[0],
        headers={
            "Content-Type": document["content_type"],
            "Content-Disposition": f'attachment; filename="{document["filename"]}"',
        },
    )


@api.get("/notifications/")
def notifications():
    try:
        limit = min(max(int(request.args.get("limit", 20)), 1), 100)
    except ValueError:
        limit = 20
    try:
        items = _store().notifications(limit)
    except Exception:  # noqa: BLE001
        logger.exception("Notification store unavailable")
        return _error("store_unavailable", _("El registro de notificaciones no está disponible."), 503)
    return jsonify({"count": len(items), "results": items})


ops = Blueprint("ops", __name__)


@ops.get("/")
def index():
    return jsonify(
        {
            "service": current_app.config["SERVICE_NAME"],
            "version": current_app.config["SERVICE_VERSION"],
            "routes": ["/health", "/api/v2/reports/", "/api/v2/reports/{task_id}/", "/api/v2/notifications/"],
        }
    )


@ops.get("/health")
def health():
    store_ok = _store().ping()
    status = "ok" if store_ok else "degraded"
    response = jsonify(
        {
            "status": status,
            "service": current_app.config["SERVICE_NAME"],
            "version": current_app.config["SERVICE_VERSION"],
            "checks": {"redis": "ok" if store_ok else "unavailable"},
        }
    )
    response.status_code = 200 if store_ok else 503
    return response


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(HTTPException)
    def _http(exc: HTTPException):
        codes = {404: "not_found", 405: "method_not_allowed", 413: "payload_too_large"}
        messages = {404: _("Recurso no encontrado."), 405: _("Método no permitido para este recurso.")}
        status = exc.code or 500
        return _error(
            codes.get(status, "http_error"),
            messages.get(status, _("La solicitud no pudo ser procesada.")),
            status,
        )

    @app.errorhandler(Exception)
    def _unexpected(exc: Exception):
        logger.exception("Unhandled error")
        return _error("internal_server_error", _("El microservicio no pudo procesar la solicitud."), 500)
