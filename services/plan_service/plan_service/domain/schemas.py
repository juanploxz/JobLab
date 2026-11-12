"""Strict, provider-independent proposal schema returned by every AI adapter."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from plan_service.domain.validators import (
    MAX_ASSUMPTION_LENGTH,
    MAX_ASSUMPTIONS,
    MAX_AVAILABLE_POSITIONS,
    MAX_COMPANY_SUMMARY_LENGTH,
    MAX_KNOWLEDGE_LENGTH,
    MAX_REQUIRED_KNOWLEDGE,
    MAX_UNIT_DESCRIPTION_LENGTH,
    MAX_VACANCY_DESCRIPTION_LENGTH,
    MIN_ASSUMPTION_LENGTH,
    MIN_AVAILABLE_POSITIONS,
    MIN_COMPANY_NAME_LENGTH,
    MIN_COMPANY_SUMMARY_LENGTH,
    MIN_KNOWLEDGE_LENGTH,
    MIN_UNIT_DESCRIPTION_LENGTH,
    MIN_UNIT_NAME_LENGTH,
    MIN_VACANCY_DESCRIPTION_LENGTH,
    MIN_VACANCY_NAME_LENGTH,
)

CODE_PATTERN = r"^[A-Z][A-Z0-9_]*$"


class StrictProposalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DepartmentProposal(StrictProposalModel):
    code: str = Field(min_length=2, max_length=40, pattern=CODE_PATTERN)
    name: str = Field(min_length=MIN_UNIT_NAME_LENGTH, max_length=120)
    description: str = Field(
        min_length=MIN_UNIT_DESCRIPTION_LENGTH,
        max_length=MAX_UNIT_DESCRIPTION_LENGTH,
    )
    parent_code: str | None = Field(default=None, min_length=2, max_length=40, pattern=CODE_PATTERN)

    @field_validator("code", "parent_code", mode="before")
    @classmethod
    def normalize_codes(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().upper().replace("-", "_").replace(" ", "_")
            if not normalized:
                raise ValueError("empty code")
            return normalized
        return value


class VacancyProposal(StrictProposalModel):
    department_code: str = Field(min_length=2, max_length=40, pattern=CODE_PATTERN)
    name: str = Field(min_length=MIN_VACANCY_NAME_LENGTH, max_length=140)
    available_positions: int = Field(ge=MIN_AVAILABLE_POSITIONS, le=MAX_AVAILABLE_POSITIONS)
    salary_min: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    salary_max: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    currency: Literal["COP", "USD", "EUR", "MXN"] = "COP"
    salary_period: Literal["HOURLY", "MONTHLY", "ANNUAL"] = "MONTHLY"
    description: str = Field(
        min_length=MIN_VACANCY_DESCRIPTION_LENGTH,
        max_length=MAX_VACANCY_DESCRIPTION_LENGTH,
    )
    required_knowledge: list[str] = Field(min_length=1, max_length=MAX_REQUIRED_KNOWLEDGE)
    reports_to: str | None = Field(default=None, max_length=140)

    @field_validator("department_code", "currency", "salary_period", mode="before")
    @classmethod
    def normalize_enums(cls, value: object) -> object:
        return value.strip().upper().replace(" ", "_") if isinstance(value, str) else value

    @field_validator("required_knowledge")
    @classmethod
    def normalize_knowledge(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            item = " ".join(value.split())
            if not MIN_KNOWLEDGE_LENGTH <= len(item) <= MAX_KNOWLEDGE_LENGTH:
                raise ValueError("invalid knowledge length")
            key = item.casefold()
            if key not in seen:
                normalized.append(item)
                seen.add(key)
        if not normalized:
            raise ValueError("at least one required knowledge item is needed")
        return normalized

    @model_validator(mode="after")
    def validate_salary_range(self) -> VacancyProposal:
        if self.salary_min > self.salary_max:
            raise ValueError("salary_min cannot exceed salary_max")
        return self


class OrganizationProposal(StrictProposalModel):
    company_name: str = Field(min_length=MIN_COMPANY_NAME_LENGTH, max_length=160)
    company_summary: str = Field(
        min_length=MIN_COMPANY_SUMMARY_LENGTH,
        max_length=MAX_COMPANY_SUMMARY_LENGTH,
    )
    assumptions: list[str] = Field(default_factory=list, max_length=MAX_ASSUMPTIONS)
    departments: list[DepartmentProposal] = Field(min_length=1, max_length=50)
    vacancies: list[VacancyProposal] = Field(min_length=1, max_length=200)

    @field_validator("assumptions")
    @classmethod
    def normalize_assumptions(cls, values: list[str]) -> list[str]:
        normalized = [" ".join(value.split()) for value in values if value and value.strip()]
        for assumption in normalized:
            if not MIN_ASSUMPTION_LENGTH <= len(assumption) <= MAX_ASSUMPTION_LENGTH:
                raise ValueError("invalid assumption length")
        return normalized

    @model_validator(mode="after")
    def validate_organization_graph(self) -> OrganizationProposal:
        by_code = {department.code: department for department in self.departments}
        if len(by_code) != len(self.departments):
            raise ValueError("department codes must be unique")

        roots = [department for department in self.departments if department.parent_code is None]
        if len(roots) != 1:
            raise ValueError("exactly one root department is required")

        for department in self.departments:
            if department.parent_code and department.parent_code not in by_code:
                raise ValueError(f"parent department {department.parent_code} does not exist")
        for department in self.departments:
            self._assert_acyclic(department.code, by_code)

        vacancy_keys: set[tuple[str, str]] = set()
        for vacancy in self.vacancies:
            if vacancy.department_code not in by_code:
                raise ValueError(f"vacancy {vacancy.name} references a missing department")
            key = (vacancy.department_code, vacancy.name.casefold())
            if key in vacancy_keys:
                raise ValueError(f"vacancy {vacancy.name} is duplicated in its department")
            vacancy_keys.add(key)
        return self

    @staticmethod
    def _assert_acyclic(start_code: str, by_code: dict[str, DepartmentProposal]) -> None:
        visited: set[str] = set()
        current: str | None = start_code
        while current is not None:
            if current in visited:
                raise ValueError("department hierarchy contains a cycle")
            visited.add(current)
            current = by_code[current].parent_code
