"""Uniform HTTP error representation for the REST presentation layer."""

from django.core.exceptions import ImproperlyConfigured
from rest_framework import status
from rest_framework.response import Response

from organization.api.serializers import APIErrorOutputSerializer
from organization.domain.exceptions import (
    DomainValidationError,
    GenerationError,
    ResourceConflictError,
    ResourceNotFoundError,
)


def error_response(
    *,
    code: str,
    detail: str,
    status_code: int,
    fields=None,
) -> Response:
    error = {"code": code, "detail": detail}
    if fields is not None:
        error["fields"] = fields
    payload = APIErrorOutputSerializer({"error": error}).data
    return Response(payload, status=status_code)


def serializer_error_response(fields) -> Response:
    return error_response(
        code="invalid_request",
        detail="La solicitud contiene datos invalidos.",
        fields=fields,
        status_code=status.HTTP_400_BAD_REQUEST,
    )


def application_error_response(exc: Exception) -> Response:
    if isinstance(exc, ResourceNotFoundError):
        return error_response(
            code=exc.code,
            detail=exc.detail,
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if isinstance(exc, ResourceConflictError):
        return error_response(
            code=exc.code,
            detail=exc.detail,
            status_code=status.HTTP_409_CONFLICT,
        )
    if isinstance(exc, DomainValidationError):
        return error_response(
            code="domain_validation_error",
            detail=str(exc),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if isinstance(exc, (GenerationError, ImproperlyConfigured)):
        return error_response(
            code="generation_service_unavailable",
            detail="El servicio de generacion no esta disponible en este momento.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    raise TypeError(f"Unsupported application exception: {type(exc).__name__}")


def child_location(request, resource_id: int) -> str:
    child_path = f"{request.path.rstrip('/')}/{resource_id}/"
    return request.build_absolute_uri(child_path)
