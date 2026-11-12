"""Uniform error contract shared with the Django API v1: {"error": {code, detail, fields?}}."""

from __future__ import annotations

import logging
from typing import Any

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from plan_service.domain.exceptions import (
    ConfigurationError,
    DomainValidationError,
    GenerationError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from plan_service.i18n import _

logger = logging.getLogger(__name__)


class InvalidRequest(Exception):
    def __init__(self, code: str, detail: str, fields: dict[str, Any] | None = None) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.fields = fields


def error_response(code: str, detail: str, status: int, fields: dict[str, Any] | None = None):
    error: dict[str, Any] = {"code": code, "detail": detail}
    if fields is not None:
        error["fields"] = fields
    return jsonify({"error": error}), status


_HTTP_CODES = {
    400: "bad_request",
    404: "not_found",
    405: "method_not_allowed",
    413: "payload_too_large",
    415: "unsupported_media_type",
    429: "throttled",
}


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(InvalidRequest)
    def _invalid_request(exc: InvalidRequest):
        return error_response(exc.code, exc.detail, 400, exc.fields)

    @app.errorhandler(DomainValidationError)
    def _domain_error(exc: DomainValidationError):
        return error_response("domain_validation_error", str(exc), 400)

    @app.errorhandler(ResourceNotFoundError)
    def _not_found(exc: ResourceNotFoundError):
        return error_response(exc.code, exc.detail, 404)

    @app.errorhandler(ResourceConflictError)
    def _conflict(exc: ResourceConflictError):
        return error_response(exc.code, exc.detail, 409)

    @app.errorhandler(GenerationError)
    @app.errorhandler(ConfigurationError)
    def _unavailable(exc: Exception):
        logger.warning("Generation unavailable: %s", exc)
        return error_response(
            "generation_service_unavailable",
            _("El servicio de generación no está disponible en este momento."),
            503,
        )

    @app.errorhandler(HTTPException)
    def _http_error(exc: HTTPException):
        status = exc.code or 500
        messages = {
            404: _("Recurso no encontrado."),
            405: _("Método no permitido para este recurso."),
            413: _("El cuerpo de la solicitud es demasiado grande."),
        }
        return error_response(
            _HTTP_CODES.get(status, "http_error"),
            messages.get(status, _("La solicitud no pudo ser procesada.")),
            status,
        )

    @app.errorhandler(Exception)
    def _unexpected(exc: Exception):
        logger.exception("Unhandled error")
        return error_response(
            "internal_server_error",
            _("El microservicio no pudo procesar la solicitud."),
            500,
        )
