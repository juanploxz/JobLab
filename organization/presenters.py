"""Presentation models for templates. Pure formatting: no business rules live here."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from organization.dtos import OrganizationalUnitDTO, PlanDetailDTO, VacancyDTO
from organization.models import OrganizationalPlan, OrganizationGenerationRequest, Vacancy


def _label(choices, value: str) -> str:
    try:
        return choices(value).label
    except ValueError:
        return value


@dataclass
class VacancyCard:
    vacancy: VacancyDTO
    status_label: str
    period_label: str
    usd_min: Decimal | None = None
    usd_max: Decimal | None = None


@dataclass
class UnitNode:
    unit: OrganizationalUnitDTO
    vacancies: list[VacancyCard] = field(default_factory=list)
    children: list[UnitNode] = field(default_factory=list)


@dataclass
class PlanPage:
    plan: PlanDetailDTO
    review_status_label: str
    generation_status_label: str
    root_units: list[UnitNode]
    conversion: dict[str, Any] | None


def review_status_label(value: str) -> str:
    return _label(OrganizationalPlan.ReviewStatus, value)


def generation_status_label(value: str) -> str:
    return _label(OrganizationGenerationRequest.Status, value)


def conversion_items(plan: PlanDetailDTO) -> list[dict[str, str]]:
    return [
        {
            "id": vacancy.id,
            "salary_min": str(vacancy.salary_min),
            "salary_max": str(vacancy.salary_max),
            "currency": vacancy.currency,
        }
        for vacancy in plan.vacancies
    ]


def build_plan_page(plan: PlanDetailDTO, conversion: dict[str, Any] | None = None) -> PlanPage:
    converted = {item["id"]: item for item in (conversion or {}).get("items", [])}
    nodes = {unit.id: UnitNode(unit=unit) for unit in plan.units}
    for vacancy in plan.vacancies:
        usd = converted.get(vacancy.id, {})
        card = VacancyCard(
            vacancy=vacancy,
            status_label=_label(Vacancy.Status, vacancy.status),
            period_label=_label(Vacancy.SalaryPeriod, vacancy.salary_period),
            usd_min=Decimal(usd["salary_min"]) if usd else None,
            usd_max=Decimal(usd["salary_max"]) if usd else None,
        )
        if vacancy.department_id in nodes:
            nodes[vacancy.department_id].vacancies.append(card)
    roots: list[UnitNode] = []
    for unit in sorted(plan.units, key=lambda item: item.name):
        node = nodes[unit.id]
        parent = nodes.get(unit.parent_id) if unit.parent_id else None
        (parent.children if parent else roots).append(node)
    return PlanPage(
        plan=plan,
        review_status_label=review_status_label(plan.review_status),
        generation_status_label=generation_status_label(plan.generation_status),
        root_units=roots,
        conversion=conversion,
    )
