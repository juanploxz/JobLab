"""Composition root for gateways. One client (and circuit breaker) per service and process."""

from __future__ import annotations

from functools import lru_cache

from django.conf import settings
from django.utils import translation

from organization.gateways.http import (
    HttpIntegrationGateway,
    HttpPlanGateway,
    HttpReportGateway,
    UnavailableGateway,
)
from organization.gateways.local import LocalPlanGateway
from organization.gateways.resilience import CircuitBreaker, ServiceClient
from organization.request_context import current_request_id


def _context_headers() -> dict[str, str]:
    headers = {"Accept-Language": translation.get_language() or settings.LANGUAGE_CODE}
    request_id = current_request_id()
    if request_id:
        headers["X-Request-ID"] = request_id
    return headers


@lru_cache(maxsize=8)
def service_client(service: str, base_url: str) -> ServiceClient:
    return ServiceClient(
        service,
        base_url,
        timeout=settings.SERVICE_TIMEOUT_SECONDS,
        breaker=CircuitBreaker(
            failure_threshold=settings.CIRCUIT_FAILURE_THRESHOLD,
            reset_seconds=settings.CIRCUIT_RESET_SECONDS,
        ),
        context=_context_headers,
    )


def build_plan_gateway():
    if settings.PLAN_SERVICE_URL:
        return HttpPlanGateway(service_client("plan-service", settings.PLAN_SERVICE_URL))
    return LocalPlanGateway()


def build_integration_gateway():
    if settings.INTEGRATION_SERVICE_URL:
        return HttpIntegrationGateway(
            service_client("integration-service", settings.INTEGRATION_SERVICE_URL)
        )
    return UnavailableGateway("integration-service")


def build_report_gateway():
    if settings.REPORT_SERVICE_URL:
        return HttpReportGateway(service_client("report-service", settings.REPORT_SERVICE_URL))
    return UnavailableGateway("report-service")


def configured_services() -> dict[str, str]:
    return {
        "plan-service": settings.PLAN_SERVICE_URL,
        "integration-service": settings.INTEGRATION_SERVICE_URL,
        "report-service": settings.REPORT_SERVICE_URL,
    }
