"""Transport-neutral application commands and result DTOs.

The REST layer serializes these immutable values; it never needs to inspect the
ORM or calculate business data itself.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CreateVacancyCommand:
    department_id: int
    name: str
    available_positions: int
    salary_min: Decimal
    salary_max: Decimal
    currency: str
    salary_period: str
    description: str
    required_knowledge: tuple[str, ...]
    reports_to: str = ""


@dataclass(frozen=True, slots=True)
class PlanMetricsDTO:
    department_count: int
    vacancy_count: int
    total_positions: int


@dataclass(frozen=True, slots=True)
class OrganizationalUnitDTO:
    id: int
    code: str
    name: str
    description: str
    parent_id: int | None


@dataclass(frozen=True, slots=True)
class VacancyDTO:
    id: int
    department_id: int
    department_name: str
    name: str
    available_positions: int
    salary_min: Decimal
    salary_max: Decimal
    currency: str
    salary_period: str
    description: str
    required_knowledge: tuple[str, ...]
    reports_to: str
    status: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PlanDetailDTO:
    id: int
    request_id: int
    company_name: str
    company_summary: str
    assumptions: tuple[str, ...]
    review_status: str
    generation_status: str
    provider_name: str
    created_at: datetime
    metrics: PlanMetricsDTO
    units: tuple[OrganizationalUnitDTO, ...]
    vacancies: tuple[VacancyDTO, ...]
