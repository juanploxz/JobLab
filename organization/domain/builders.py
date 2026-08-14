from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import ValidationError

from organization.domain.exceptions import DomainValidationError
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
        self._data["name"] = " ".join((name or "").split())
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
        self._data["description"] = " ".join((description or "").split())
        return self

    def requiring(self, knowledge: list[str]) -> "VacancyBuilder":
        normalized = [" ".join(item.split()) for item in knowledge if item and item.strip()]
        self._data["required_knowledge"] = list(dict.fromkeys(normalized))
        return self

    def reporting_to(self, role_name: str | None) -> "VacancyBuilder":
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
        if self._data["department"].plan_id != self._data["plan"].id:
            raise DomainValidationError("El departamento no pertenece al plan indicado")
        if self._data["available_positions"] < 1:
            raise DomainValidationError("La cantidad de puestos debe ser mayor que cero")
        if self._data["salary_min"] > self._data["salary_max"]:
            raise DomainValidationError("El salario minimo no puede superar el maximo")
        if len(self._data["description"]) < 50:
            raise DomainValidationError("La descripcion de la vacante es demasiado corta")
        if not self._data["required_knowledge"]:
            raise DomainValidationError("Debe existir al menos un conocimiento requerido")
