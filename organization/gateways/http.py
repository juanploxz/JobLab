"""Remote adapters: translate the microservices' JSON contracts into Django-side DTOs."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from django.utils.translation import gettext as _

from organization.domain.exceptions import (
    DomainValidationError,
    GenerationError,
    ResourceNotFoundError,
    ServiceUnavailableError,
)
from organization.dtos import (
    OrganizationalUnitDTO,
    PlanDetailDTO,
    PlanMetricsDTO,
    PlanPageDTO,
    PlanSummaryDTO,
    VacancyDTO,
)
from organization.gateways.resilience import ServiceClient, error_detail


def _datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _vacancy(data: dict[str, Any]) -> VacancyDTO:
    return VacancyDTO(
        id=data["id"],
        department_id=data["department_id"],
        department_name=data["department_name"],
        name=data["name"],
        available_positions=data["available_positions"],
        salary_min=Decimal(data["salary_min"]),
        salary_max=Decimal(data["salary_max"]),
        currency=data["currency"],
        salary_period=data["salary_period"],
        description=data["description"],
        required_knowledge=tuple(data.get("required_knowledge", [])),
        reports_to=data.get("reports_to") or "",
        status=data["status"],
        created_at=_datetime(data.get("created_at")),
    )


def plan_from_json(data: dict[str, Any]) -> PlanDetailDTO:
    metrics = data.get("metrics", {})
    return PlanDetailDTO(
        id=data["id"],
        request_id=data["request_id"],
        company_name=data["company_name"],
        company_summary=data["company_summary"],
        assumptions=tuple(data.get("assumptions", [])),
        review_status=data["review_status"],
        generation_status=data["generation_status"],
        provider_name=data["provider_name"],
        created_at=_datetime(data.get("created_at")),
        metrics=PlanMetricsDTO(
            department_count=metrics.get("department_count", 0),
            vacancy_count=metrics.get("vacancy_count", 0),
            total_positions=metrics.get("total_positions", 0),
        ),
        units=tuple(
            OrganizationalUnitDTO(
                id=unit["id"],
                code=unit["code"],
                name=unit["name"],
                description=unit["description"],
                parent_id=unit.get("parent_id"),
            )
            for unit in data.get("units", [])
        ),
        vacancies=tuple(_vacancy(item) for item in data.get("vacancies", [])),
    )


class HttpPlanGateway:
    name = "plan-service"

    def __init__(self, client: ServiceClient) -> None:
        self._client = client

    def generate_plan(self, company_description: str) -> int:
        try:
            response = self._client.request(
                "POST", "/api/v2/plans/", json={"company_description": company_description}
            )
        except ServiceUnavailableError as exc:
            raise GenerationError(
                _("El servicio de generación no está disponible. Intenta nuevamente más tarde.")
            ) from exc
        if response.status_code == 201:
            return int(response.json()["id"])
        code, detail = error_detail(response, _("La solicitud no pudo ser procesada."))
        if response.status_code == 400:
            raise DomainValidationError(detail)
        raise GenerationError(detail)

    def get_plan(self, plan_id: int) -> PlanDetailDTO:
        response = self._client.request("GET", f"/api/v2/plans/{int(plan_id)}/")
        if response.status_code == 404:
            code, detail = error_detail(response, _("Recurso no encontrado."))
            raise ResourceNotFoundError(detail, code=code or "plan_not_found")
        if response.status_code != 200:
            raise ServiceUnavailableError(self.name, f"HTTP {response.status_code}")
        return plan_from_json(response.json())

    def list_plans(self, page: int, page_size: int) -> PlanPageDTO:
        response = self._client.request(
            "GET", "/api/v2/plans/", params={"page": page, "page_size": page_size}
        )
        if response.status_code == 404:
            raise ResourceNotFoundError(_("Página inválida."), code="page_not_found")
        if response.status_code != 200:
            raise ServiceUnavailableError(self.name, f"HTTP {response.status_code}")
        body = response.json()
        items = tuple(
            PlanSummaryDTO(
                id=item["id"],
                company_name=item["company_name"],
                company_summary=item.get("company_summary", ""),
                review_status=item["review_status"],
                generation_status=item["generation_status"],
                provider_name=item["provider_name"],
                created_at=_datetime(item.get("created_at")),
            )
            for item in body.get("results", [])
        )
        return PlanPageDTO(items=items, count=body.get("count", 0), page=page, page_size=page_size)


class HttpIntegrationGateway:
    name = "integration-service"

    def __init__(self, client: ServiceClient) -> None:
        self._client = client

    def convert_salaries(self, target: str, vacancies: list[dict[str, Any]]) -> dict[str, Any]:
        response = self._client.request(
            "POST", "/api/v2/salaries/convert/", json={"target": target, "items": vacancies}
        )
        if response.status_code != 200:
            raise ServiceUnavailableError(self.name, f"HTTP {response.status_code}")
        return response.json()

    def ally_catalog(self) -> dict[str, Any]:
        # A 503 here describes the allied service, not integration-service: keep the circuit closed.
        response = self._client.request("GET", "/api/v2/ally/", passthrough=(503,))
        if response.status_code == 503:
            code, detail = error_detail(response, "")
            raise ServiceUnavailableError(self.name, code or detail)
        if response.status_code != 200:
            raise ServiceUnavailableError(self.name, f"HTTP {response.status_code}")
        return response.json()


class HttpReportGateway:
    name = "report-service"

    def __init__(self, client: ServiceClient) -> None:
        self._client = client

    def request_report(self, plan_id: int, report_format: str) -> dict[str, Any]:
        response = self._client.request(
            "POST", "/api/v2/reports/", json={"plan_id": int(plan_id), "format": report_format}
        )
        if response.status_code == 400:
            raise DomainValidationError(error_detail(response, _("La solicitud no pudo ser procesada."))[1])
        if response.status_code != 202:
            raise ServiceUnavailableError(self.name, f"HTTP {response.status_code}")
        return response.json()

    def report_status(self, task_id: str) -> dict[str, Any]:
        response = self._client.request("GET", f"/api/v2/reports/{task_id}/")
        if response.status_code == 404:
            raise ResourceNotFoundError(_("No existe un reporte con ese identificador."), code="report_not_found")
        if response.status_code != 200:
            raise ServiceUnavailableError(self.name, f"HTTP {response.status_code}")
        return response.json()

    def download(self, task_id: str) -> tuple[bytes, str, str]:
        response = self._client.request("GET", f"/api/v2/reports/{task_id}/download/")
        if response.status_code in (404, 409):
            raise ResourceNotFoundError(_("El reporte todavía no está disponible."), code="report_not_ready")
        if response.status_code != 200:
            raise ServiceUnavailableError(self.name, f"HTTP {response.status_code}")
        return (
            response.content,
            response.headers.get("Content-Type", "application/octet-stream"),
            response.headers.get("Content-Disposition", "attachment"),
        )

    def notifications(self, limit: int = 20) -> list[dict[str, Any]]:
        response = self._client.request("GET", "/api/v2/notifications/", params={"limit": limit})
        if response.status_code != 200:
            raise ServiceUnavailableError(self.name, f"HTTP {response.status_code}")
        return response.json().get("results", [])


class UnavailableGateway:
    """Null Object used when a microservice URL is not configured."""

    def __init__(self, service: str) -> None:
        self.name = service

    def __getattr__(self, attribute: str):
        def _unavailable(*args: Any, **kwargs: Any):
            raise ServiceUnavailableError(self.name, "not configured")

        return _unavailable
