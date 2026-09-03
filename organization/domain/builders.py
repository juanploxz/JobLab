from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import ValidationError

from organization.domain.exceptions import DomainValidationError
from organization.domain.validators import (
    MAX_AVAILABLE_POSITIONS,
    MAX_KNOWLEDGE_LENGTH,
    MAX_REQUIRED_KNOWLEDGE,
    MAX_VACANCY_DESCRIPTION_LENGTH,
    MIN_AVAILABLE_POSITIONS,
    MIN_KNOWLEDGE_LENGTH,
    MIN_VACANCY_DESCRIPTION_LENGTH,
    MIN_VACANCY_NAME_LENGTH,
)
from organization.models import OrganizationalPlan, OrganizationalUnit, Vacancy


class VacancyBuilder:
    """Build an unsaved, fully validated Vacancy through a fluent interface."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {"status": Vacancy.Status.DRAFT}

    def for_plan(self, plan: OrganizationalPlan) -> "VacancyBuilder":
        self._data["plan"] = plan
        return self

    def in_department(self, department: OrganizationalUnit) -> "VacancyBuilder":
        self._data["department"] = department
        return self

    def with_name(self, name: str) -> "VacancyBuilder":
        if not isinstance(name, str):
            raise DomainValidationError("El nombre de la vacante debe ser texto")
        self._data["name"] = " ".join(name.split())
        return self

    def with_positions(self, amount: int) -> "VacancyBuilder":
        self._data["available_positions"] = amount
        return self

    def with_salary(
        self,
        minimum: Decimal | str | int,
        maximum: Decimal | str | int,
        currency: str,
        period: str = Vacancy.SalaryPeriod.MONTHLY,
    ) -> "VacancyBuilder":
        try:
            self._data["salary_min"] = Decimal(str(minimum))
            self._data["salary_max"] = Decimal(str(maximum))
        except (InvalidOperation, TypeError) as exc:
            raise DomainValidationError("El salario debe ser numerico") from exc
        self._data["currency"] = currency
        self._data["salary_period"] = period
        return self

    def with_description(self, description: str) -> "VacancyBuilder":
        if not isinstance(description, str):
            raise DomainValidationError("La descripcion de la vacante debe ser texto")
        self._data["description"] = " ".join(description.split())
        return self

    def requiring(self, knowledge: list[str]) -> "VacancyBuilder":
        if not isinstance(knowledge, list):
            raise DomainValidationError("Los conocimientos requeridos deben ser una lista")

        normalized: list[str] = []
        seen: set[str] = set()
        for item in knowledge:
            if not isinstance(item, str):
                raise DomainValidationError("Cada conocimiento requerido debe ser texto")
            value = " ".join(item.split())
            if not value:
                continue
            key = value.casefold()
            if key not in seen:
                normalized.append(value)
                seen.add(key)
        self._data["required_knowledge"] = normalized
        return self

    def reporting_to(self, role_name: str | None) -> "VacancyBuilder":
        if role_name is not None and not isinstance(role_name, str):
            raise DomainValidationError("El rol de reporte debe ser texto")
        self._data["reports_to"] = " ".join((role_name or "").split())
        return self

    def build(self) -> Vacancy:
        self._validate_business_rules()
        vacancy = Vacancy(**self._data)
        try:
            vacancy.full_clean()
        except ValidationError as exc:
            raise DomainValidationError(
                f"La vacante no supera la validacion del modelo: {exc.message_dict}"
            ) from exc
        return vacancy

    def _validate_business_rules(self) -> None:
        required_fields = {
            "plan",
            "department",
            "name",
            "available_positions",
            "salary_min",
            "salary_max",
            "currency",
            "salary_period",
            "description",
            "required_knowledge",
        }
        missing = sorted(required_fields.difference(self._data))
        if missing:
            raise DomainValidationError(f"Faltan campos obligatorios: {', '.join(missing)}")
        if not isinstance(self._data["plan"], OrganizationalPlan):
            raise DomainValidationError("El plan indicado no es valido")
        if not isinstance(self._data["department"], OrganizationalUnit):
            raise DomainValidationError("El departamento indicado no es valido")
        if self._data["department"].plan_id != self._data["plan"].id:
            raise DomainValidationError("El departamento no pertenece al plan indicado")
        positions = self._data["available_positions"]
        if isinstance(positions, bool) or not isinstance(positions, int):
            raise DomainValidationError("La cantidad de puestos debe ser un numero entero")
        if not MIN_AVAILABLE_POSITIONS <= positions <= MAX_AVAILABLE_POSITIONS:
            raise DomainValidationError(
                "La cantidad de puestos debe estar entre "
                f"{MIN_AVAILABLE_POSITIONS} y {MAX_AVAILABLE_POSITIONS}"
            )
        if len(self._data["name"]) < MIN_VACANCY_NAME_LENGTH:
            raise DomainValidationError("El nombre de la vacante es demasiado corto")
        if not self._data["salary_min"].is_finite() or not self._data["salary_max"].is_finite():
            raise DomainValidationError("El salario debe ser un numero finito")
        if self._data["salary_min"] < 0:
            raise DomainValidationError("El salario minimo no puede ser negativo")
        if self._data["salary_min"] > self._data["salary_max"]:
            raise DomainValidationError("El salario minimo no puede superar el maximo")
        description_length = len(self._data["description"])
        valid_description_length = (
            MIN_VACANCY_DESCRIPTION_LENGTH
            <= description_length
            <= MAX_VACANCY_DESCRIPTION_LENGTH
        )
        if not valid_description_length:
            raise DomainValidationError(
                "La descripcion de la vacante debe tener entre "
                f"{MIN_VACANCY_DESCRIPTION_LENGTH} y "
                f"{MAX_VACANCY_DESCRIPTION_LENGTH} caracteres"
            )
        knowledge = self._data["required_knowledge"]
        if not knowledge:
            raise DomainValidationError("Debe existir al menos un conocimiento requerido")
        if len(knowledge) > MAX_REQUIRED_KNOWLEDGE:
            raise DomainValidationError(
                f"No puede haber mas de {MAX_REQUIRED_KNOWLEDGE} conocimientos requeridos"
            )
        if any(
            not MIN_KNOWLEDGE_LENGTH <= len(item) <= MAX_KNOWLEDGE_LENGTH
            for item in knowledge
        ):
            raise DomainValidationError(
                "Cada conocimiento debe tener entre "
                f"{MIN_KNOWLEDGE_LENGTH} y {MAX_KNOWLEDGE_LENGTH} caracteres"
            )
