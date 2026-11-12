"""Builder for the most complex entity of the bounded context (migrated from Django)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from plan_service.domain.exceptions import DomainValidationError
from plan_service.domain.validators import (
    CURRENCIES,
    MAX_AVAILABLE_POSITIONS,
    MAX_KNOWLEDGE_LENGTH,
    MAX_REPORTS_TO_LENGTH,
    MAX_REQUIRED_KNOWLEDGE,
    MAX_VACANCY_DESCRIPTION_LENGTH,
    MAX_VACANCY_NAME_LENGTH,
    MIN_AVAILABLE_POSITIONS,
    MIN_KNOWLEDGE_LENGTH,
    MIN_VACANCY_DESCRIPTION_LENGTH,
    MIN_VACANCY_NAME_LENGTH,
    SALARY_PERIODS,
    normalize_spaces,
)
from plan_service.i18n import _
from plan_service.models import Plan, Unit, Vacancy

_REQUIRED_FIELDS = frozenset(
    {
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
)


class VacancyBuilder:
    """Build an unsaved, fully validated Vacancy through a fluent interface."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {"status": Vacancy.DRAFT, "reports_to": ""}

    def for_plan(self, plan: Plan) -> VacancyBuilder:
        self._data["plan"] = plan
        return self

    def in_department(self, department: Unit) -> VacancyBuilder:
        self._data["department"] = department
        return self

    def with_name(self, name: str) -> VacancyBuilder:
        if not isinstance(name, str):
            raise DomainValidationError(_("El nombre de la vacante debe ser texto."))
        self._data["name"] = normalize_spaces(name)
        return self

    def with_positions(self, amount: int) -> VacancyBuilder:
        self._data["available_positions"] = amount
        return self

    def with_salary(
        self,
        minimum: Decimal | str | int,
        maximum: Decimal | str | int,
        currency: str,
        period: str = "MONTHLY",
    ) -> VacancyBuilder:
        try:
            self._data["salary_min"] = Decimal(str(minimum))
            self._data["salary_max"] = Decimal(str(maximum))
        except (InvalidOperation, TypeError) as exc:
            raise DomainValidationError(_("El salario debe ser numérico.")) from exc
        self._data["currency"] = (currency or "").strip().upper()
        self._data["salary_period"] = (period or "").strip().upper()
        return self

    def with_description(self, description: str) -> VacancyBuilder:
        if not isinstance(description, str):
            raise DomainValidationError(_("La descripción de la vacante debe ser texto."))
        self._data["description"] = normalize_spaces(description)
        return self

    def requiring(self, knowledge: list[str]) -> VacancyBuilder:
        if not isinstance(knowledge, list):
            raise DomainValidationError(_("Los conocimientos requeridos deben ser una lista."))
        normalized: list[str] = []
        seen: set[str] = set()
        for item in knowledge:
            if not isinstance(item, str):
                raise DomainValidationError(_("Cada conocimiento requerido debe ser texto."))
            value = normalize_spaces(item)
            if value and value.casefold() not in seen:
                normalized.append(value)
                seen.add(value.casefold())
        self._data["required_knowledge"] = normalized
        return self

    def reporting_to(self, role_name: str | None) -> VacancyBuilder:
        if role_name is not None and not isinstance(role_name, str):
            raise DomainValidationError(_("El rol de reporte debe ser texto."))
        self._data["reports_to"] = normalize_spaces(role_name or "")
        return self

    def build(self) -> Vacancy:
        self._validate()
        data = dict(self._data)
        data["name_key"] = data["name"].casefold()
        return Vacancy(**data)

    def _validate(self) -> None:
        missing = sorted(_REQUIRED_FIELDS.difference(self._data))
        if missing:
            raise DomainValidationError(
                _("Faltan campos obligatorios: %(fields)s.", fields=", ".join(missing))
            )
        plan, department = self._data["plan"], self._data["department"]
        if not isinstance(plan, Plan):
            raise DomainValidationError(_("El plan indicado no es válido."))
        if not isinstance(department, Unit):
            raise DomainValidationError(_("El departamento indicado no es válido."))
        if department.plan is not plan and department.plan_id != plan.id:
            raise DomainValidationError(_("El departamento no pertenece al plan indicado."))

        positions = self._data["available_positions"]
        if isinstance(positions, bool) or not isinstance(positions, int):
            raise DomainValidationError(_("La cantidad de puestos debe ser un número entero."))
        if not MIN_AVAILABLE_POSITIONS <= positions <= MAX_AVAILABLE_POSITIONS:
            raise DomainValidationError(
                _(
                    "La cantidad de puestos debe estar entre %(minimum)s y %(maximum)s.",
                    minimum=MIN_AVAILABLE_POSITIONS,
                    maximum=MAX_AVAILABLE_POSITIONS,
                )
            )
        if not MIN_VACANCY_NAME_LENGTH <= len(self._data["name"]) <= MAX_VACANCY_NAME_LENGTH:
            raise DomainValidationError(
                _(
                    "El nombre de la vacante debe tener entre %(minimum)s y %(maximum)s caracteres.",
                    minimum=MIN_VACANCY_NAME_LENGTH,
                    maximum=MAX_VACANCY_NAME_LENGTH,
                )
            )

        salary_min, salary_max = self._data["salary_min"], self._data["salary_max"]
        if not salary_min.is_finite() or not salary_max.is_finite():
            raise DomainValidationError(_("El salario debe ser un número finito."))
        if salary_min < 0:
            raise DomainValidationError(_("El salario mínimo no puede ser negativo."))
        if salary_min > salary_max:
            raise DomainValidationError(_("El salario mínimo no puede superar el máximo."))
        if self._data["currency"] not in CURRENCIES:
            raise DomainValidationError(
                _("La moneda debe ser una de: %(options)s.", options=", ".join(CURRENCIES))
            )
        if self._data["salary_period"] not in SALARY_PERIODS:
            raise DomainValidationError(
                _("La periodicidad debe ser una de: %(options)s.", options=", ".join(SALARY_PERIODS))
            )

        description_length = len(self._data["description"])
        if not MIN_VACANCY_DESCRIPTION_LENGTH <= description_length <= MAX_VACANCY_DESCRIPTION_LENGTH:
            raise DomainValidationError(
                _(
                    "La descripción de la vacante debe tener entre %(minimum)s y %(maximum)s caracteres.",
                    minimum=MIN_VACANCY_DESCRIPTION_LENGTH,
                    maximum=MAX_VACANCY_DESCRIPTION_LENGTH,
                )
            )

        knowledge = self._data["required_knowledge"]
        if not knowledge:
            raise DomainValidationError(_("Debe existir al menos un conocimiento requerido."))
        if len(knowledge) > MAX_REQUIRED_KNOWLEDGE:
            raise DomainValidationError(
                _(
                    "No puede haber más de %(maximum)s conocimientos requeridos.",
                    maximum=MAX_REQUIRED_KNOWLEDGE,
                )
            )
        if any(not MIN_KNOWLEDGE_LENGTH <= len(item) <= MAX_KNOWLEDGE_LENGTH for item in knowledge):
            raise DomainValidationError(
                _(
                    "Cada conocimiento debe tener entre %(minimum)s y %(maximum)s caracteres.",
                    minimum=MIN_KNOWLEDGE_LENGTH,
                    maximum=MAX_KNOWLEDGE_LENGTH,
                )
            )
        if len(self._data["reports_to"]) > MAX_REPORTS_TO_LENGTH:
            raise DomainValidationError(
                _(
                    "El rol de reporte no puede superar %(maximum)s caracteres.",
                    maximum=MAX_REPORTS_TO_LENGTH,
                )
            )
