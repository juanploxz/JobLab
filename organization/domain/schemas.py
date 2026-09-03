from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from organization.domain.validators import (
    MAX_ASSUMPTION_LENGTH,
    MAX_ASSUMPTIONS,
    MAX_AVAILABLE_POSITIONS,
    MAX_COMPANY_SUMMARY_LENGTH,
    MAX_KNOWLEDGE_LENGTH,
    MAX_REQUIRED_KNOWLEDGE,
    MAX_UNIT_DESCRIPTION_LENGTH,
    MAX_VACANCY_DESCRIPTION_LENGTH,
    MIN_AVAILABLE_POSITIONS,
    MIN_ASSUMPTION_LENGTH,
    MIN_COMPANY_NAME_LENGTH,
    MIN_COMPANY_SUMMARY_LENGTH,
    MIN_KNOWLEDGE_LENGTH,
    MIN_UNIT_DESCRIPTION_LENGTH,
    MIN_UNIT_NAME_LENGTH,
    MIN_VACANCY_DESCRIPTION_LENGTH,
    MIN_VACANCY_NAME_LENGTH,
)


class StrictProposalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DepartmentProposal(StrictProposalModel):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[A-Z][A-Z0-9_]*$")
    name: str = Field(min_length=MIN_UNIT_NAME_LENGTH, max_length=120)
    description: str = Field(
        min_length=MIN_UNIT_DESCRIPTION_LENGTH,
        max_length=MAX_UNIT_DESCRIPTION_LENGTH,
    )
    parent_code: str | None = Field(
        default=None,
        min_length=2,
        max_length=40,
        pattern=r"^[A-Z][A-Z0-9_]*$",
    )

    @field_validator("code", "parent_code", mode="before")
    @classmethod
    def normalize_codes(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().upper().replace("-", "_").replace(" ", "_")
            if not normalized:
                raise ValueError("El codigo no puede estar vacio")
            return normalized
        return value


class VacancyProposal(StrictProposalModel):
    department_code: str = Field(
        min_length=2,
        max_length=40,
        pattern=r"^[A-Z][A-Z0-9_]*$",
    )
    name: str = Field(min_length=MIN_VACANCY_NAME_LENGTH, max_length=140)
    available_positions: int = Field(
        ge=MIN_AVAILABLE_POSITIONS,
        le=MAX_AVAILABLE_POSITIONS,
    )
    salary_min: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    salary_max: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    currency: Literal["COP", "USD", "EUR", "MXN"] = "COP"
    salary_period: Literal["HOURLY", "MONTHLY", "ANNUAL"] = "MONTHLY"
    description: str = Field(
        min_length=MIN_VACANCY_DESCRIPTION_LENGTH,
        max_length=MAX_VACANCY_DESCRIPTION_LENGTH,
    )
    required_knowledge: list[str] = Field(
        min_length=1,
        max_length=MAX_REQUIRED_KNOWLEDGE,
    )
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
                raise ValueError(
                    "Cada conocimiento debe tener entre "
                    f"{MIN_KNOWLEDGE_LENGTH} y {MAX_KNOWLEDGE_LENGTH} caracteres"
                )
            key = item.casefold()
            if key not in seen:
                normalized.append(item)
                seen.add(key)
        if not normalized:
            raise ValueError("Debe existir al menos un conocimiento requerido")
        return normalized

    @model_validator(mode="after")
    def validate_salary_range(self) -> "VacancyProposal":
        if self.salary_min > self.salary_max:
            raise ValueError("El salario minimo no puede superar el salario maximo")
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
                raise ValueError(
                    "Cada supuesto debe tener entre "
                    f"{MIN_ASSUMPTION_LENGTH} y {MAX_ASSUMPTION_LENGTH} caracteres"
                )
        return normalized

    @model_validator(mode="after")
    def validate_organization_graph(self) -> "OrganizationProposal":
        departments_by_code = {department.code: department for department in self.departments}
        if len(departments_by_code) != len(self.departments):
            raise ValueError("Los codigos de departamento deben ser unicos")

        roots = [department for department in self.departments if department.parent_code is None]
        if len(roots) != 1:
            raise ValueError("La estructura debe contener exactamente un departamento raiz")

        for department in self.departments:
            if department.parent_code and department.parent_code not in departments_by_code:
                raise ValueError(
                    f"El departamento padre {department.parent_code} no existe"
                )

        for department in self.departments:
            self._assert_acyclic(department.code, departments_by_code)

        vacancy_keys: set[tuple[str, str]] = set()
        for vacancy in self.vacancies:
            if vacancy.department_code not in departments_by_code:
                raise ValueError(
                    f"La vacante {vacancy.name} apunta a un departamento inexistente"
                )
            key = (vacancy.department_code, vacancy.name.casefold())
            if key in vacancy_keys:
                raise ValueError(
                    f"La vacante {vacancy.name} esta duplicada en el mismo departamento"
                )
            vacancy_keys.add(key)
        return self

    @staticmethod
    def _assert_acyclic(
        start_code: str,
        departments_by_code: dict[str, DepartmentProposal],
    ) -> None:
        visited: set[str] = set()
        current_code: str | None = start_code
        while current_code is not None:
            if current_code in visited:
                raise ValueError("La jerarquia de departamentos contiene un ciclo")
            visited.add(current_code)
            current_department = departments_by_code.get(current_code)
            if current_department is None:
                raise ValueError(f"El departamento padre {current_code} no existe")
            current_code = current_department.parent_code
