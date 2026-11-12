"""HTTP adapter of the integration microservice."""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any

from flask import Blueprint, Flask, current_app, jsonify, request
from werkzeug.exceptions import HTTPException

from integration_service.domain import (
    IntegrationNotConfiguredError,
    ProviderUnavailableError,
    RateTable,
    UnsupportedCurrencyError,
)
from integration_service.i18n import _
from integration_service.services import (
    ConvertSalariesService,
    GetAllyCatalogService,
    GetExchangeRatesService,
    InvalidConversionRequest,
)

logger = logging.getLogger(__name__)

EXCHANGE_KEY = "joblab.exchange_provider"
ALLY_KEY = "joblab.ally_catalog"

api = Blueprint("integration", __name__)


def _error(code: str, detail: str, status: int):
    return jsonify({"error": {"code": code, "detail": detail}}), status


def _decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _table_payload(table: RateTable) -> dict[str, Any]:
    return {
        "base": table.base,
        "provider": table.provider,
        "fetched_at": table.fetched_at.isoformat(),
        "stale": table.stale,
        "rates": {code: _decimal(rate.quantize(Decimal("0.000001"))) for code, rate in sorted(table.rates.items())},
    }


@api.get("/rates/")
def rates():
    symbols = tuple(s for s in (request.args.get("symbols") or "").split(",") if s.strip())
    service = GetExchangeRatesService(current_app.extensions[EXCHANGE_KEY])
    table = service.execute(request.args.get("base", "USD"), symbols)
    return jsonify(_table_payload(table))


@api.post("/salaries/convert/")
def convert_salaries():
    try:
        payload = json.loads(request.get_data(as_text=True) or "{}")
    except json.JSONDecodeError:
        return _error("parse_error", _("El cuerpo JSON está mal formado."), 400)
    if not isinstance(payload, dict):
        return _error("invalid_request", _("El cuerpo debe ser un objeto JSON."), 400)
    service = ConvertSalariesService(
        current_app.extensions[EXCHANGE_KEY], max_items=current_app.config["MAX_BATCH_ITEMS"]
    )
    target = str(payload.get("target") or "").upper()
    table, items = service.execute(target, payload.get("items", []))
    return jsonify(
        {
            "target": target,
            "provider": table.provider,
            "fetched_at": table.fetched_at.isoformat(),
            "stale": table.stale,
            "items": [
                {
                    "id": item.id,
                    "salary_min": f"{item.salary_min:.2f}",
                    "salary_max": f"{item.salary_max:.2f}",
                    "original_currency": item.original_currency,
                    "rate": _decimal(item.rate.quantize(Decimal("0.00000001"))),
                }
                for item in items
            ],
        }
    )


@api.get("/ally/")
def ally_catalog():
    catalog = GetAllyCatalogService(current_app.extensions[ALLY_KEY]).execute()
    return jsonify(
        {
            "ally": catalog.ally_name,
            "source": catalog.source_url,
            "fetched_at": catalog.fetched_at.isoformat(),
            "stale": catalog.stale,
            "count": len(catalog.items),
            "items": [
                {
                    "title": item.title,
                    "subtitle": item.subtitle,
                    "description": item.description,
                    "url": item.url,
                }
                for item in catalog.items
            ],
        }
    )


ops = Blueprint("ops", __name__)


@ops.get("/")
def index():
    return jsonify(
        {
            "service": current_app.config["SERVICE_NAME"],
            "version": current_app.config["SERVICE_VERSION"],
            "routes": ["/health", "/api/v2/rates/", "/api/v2/salaries/convert/", "/api/v2/ally/"],
        }
    )


@ops.get("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "service": current_app.config["SERVICE_NAME"],
            "version": current_app.config["SERVICE_VERSION"],
            "checks": {
                "exchange_providers": current_app.config["EXCHANGE_PROVIDERS"],
                "ally_configured": bool(current_app.config["ALLY_SERVICE_URL"]),
            },
        }
    )


_CONVERSION_MESSAGES = {
    "unsupported_target": lambda p: _("La moneda destino debe ser una de: %(options)s.", **p),
    "invalid_items": lambda p: _(
        "items debe ser una lista de máximo %(maximum)s salarios con salary_min, salary_max y currency.",
        **p,
    ),
    "invalid_range": lambda p: _("Cada rango salarial debe ser numérico, no negativo y ordenado."),
}


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(InvalidConversionRequest)
    def _invalid(exc: InvalidConversionRequest):
        return _error("invalid_request", _CONVERSION_MESSAGES[exc.detail_key](exc.params), 400)

    @app.errorhandler(UnsupportedCurrencyError)
    def _unsupported(exc: UnsupportedCurrencyError):
        return _error(
            "unsupported_currency",
            _("La moneda %(currency)s no está disponible.", currency=exc.currency),
            400,
        )

    @app.errorhandler(IntegrationNotConfiguredError)
    def _not_configured(exc: IntegrationNotConfiguredError):
        return _error(
            "ally_not_configured",
            _("La integración con el equipo aliado aún no está configurada."),
            503,
        )

    @app.errorhandler(ProviderUnavailableError)
    def _unavailable(exc: ProviderUnavailableError):
        logger.warning("External provider unavailable: %s", exc)
        return _error(
            "provider_unavailable",
            _("El proveedor externo no está disponible en este momento."),
            503,
        )

    @app.errorhandler(HTTPException)
    def _http(exc: HTTPException):
        codes = {404: "not_found", 405: "method_not_allowed", 413: "payload_too_large"}
        messages = {
            404: _("Recurso no encontrado."),
            405: _("Método no permitido para este recurso."),
        }
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
