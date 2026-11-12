"""Output representation: DTO -> JSON-compatible dictionaries."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from plan_service.dtos import PlanDetailDTO, PlanMetricsDTO, PlanSummaryDTO, UnitDTO, VacancyDTO


def money(value: Decimal) -> str:
    return f"{Decimal(value):.2f}"


def timestamp(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def metrics(dto: PlanMetricsDTO) -> dict[str, int]:
    return {
        "department_count": dto.department_count,
        "vacancy_count": dto.vacancy_count,
        "total_positions": dto.total_positions,
    }


def unit(dto: UnitDTO) -> dict[str, Any]:
    return {
        "id": dto.id,
        "code": dto.code,
        "name": dto.name,
        "description": dto.description,
        "parent_id": dto.parent_id,
    }


def vacancy(dto: VacancyDTO) -> dict[str, Any]:
    return {
        "id": dto.id,
        "plan_id": dto.plan_id,
        "department_id": dto.department_id,
        "department_name": dto.department_name,
        "name": dto.name,
        "available_positions": dto.available_positions,
        "salary_min": money(dto.salary_min),
        "salary_max": money(dto.salary_max),
        "currency": dto.currency,
        "salary_period": dto.salary_period,
        "description": dto.description,
        "required_knowledge": list(dto.required_knowledge),
        "reports_to": dto.reports_to,
        "status": dto.status,
        "created_at": timestamp(dto.created_at),
    }


def plan_summary(dto: PlanSummaryDTO) -> dict[str, Any]:
    return {
        "id": dto.id,
        "company_name": dto.company_name,
        "company_summary": dto.company_summary,
        "review_status": dto.review_status,
        "generation_status": dto.generation_status,
        "provider_name": dto.provider_name,
        "created_at": timestamp(dto.created_at),
    }


def plan_detail(dto: PlanDetailDTO) -> dict[str, Any]:
    return {
        "id": dto.id,
        "request_id": dto.request_id,
        "company_name": dto.company_name,
        "company_summary": dto.company_summary,
        "assumptions": list(dto.assumptions),
        "review_status": dto.review_status,
        "generation_status": dto.generation_status,
        "provider_name": dto.provider_name,
        "created_at": timestamp(dto.created_at),
        "metrics": metrics(dto.metrics),
        "units": [unit(item) for item in dto.units],
        "vacancies": [vacancy(item) for item in dto.vacancies],
    }


def public_summary(data: dict[str, Any]) -> dict[str, Any]:
    latest = []
    for item in data["latest_vacancies"]:
        latest.append(
            {**item, "salary_min": money(item["salary_min"]), "salary_max": money(item["salary_max"])}
        )
    return {**data, "latest_vacancies": latest}
