import logging
from collections.abc import Callable
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.db.models import Prefetch, QuerySet
from django.utils import timezone

from organization.domain.builders import VacancyBuilder
from organization.domain.exceptions import (
    GenerationError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from organization.domain.ports import OrganizationGenerator
from organization.domain.schemas import OrganizationProposal
from organization.domain.validators import validate_company_description
from organization.dtos import (
    CreateVacancyCommand,
    OrganizationalUnitDTO,
    PlanDetailDTO,
    PlanMetricsDTO,
    VacancyDTO,
)
from organization.models import (
    OrganizationalPlan,
    OrganizationalUnit,
    OrganizationGenerationRequest,
    Vacancy,
)

logger = logging.getLogger(__name__)


class GenerateOrganizationService:
    """Application service that orchestrates one complete generation use case."""

    def __init__(self, ai_provider: OrganizationGenerator) -> None:
        self.ai_provider = ai_provider

    def execute(self, company_description: str) -> OrganizationalPlan:
        description = validate_company_description(company_description)
        generation_request = OrganizationGenerationRequest.objects.create(
            company_description=description,
            provider_name=self.ai_provider.name,
        )
        generation_request.status = OrganizationGenerationRequest.Status.PROCESSING
        generation_request.save(update_fields=("status",))

        try:
            proposal = OrganizationProposal.model_validate(
                self.ai_provider.generate(description)
            )
            with transaction.atomic():
                plan = self._create_plan(generation_request, proposal)
                departments = self._create_departments(plan, proposal)
                self._create_vacancies(plan, departments, proposal)
                generation_request.status = OrganizationGenerationRequest.Status.COMPLETED
                generation_request.completed_at = timezone.now()
                generation_request.error_message = ""
                generation_request.save(
                    update_fields=("status", "completed_at", "error_message")
                )
            return plan
        except Exception as exc:
            logger.exception("Organization generation failed for request %s", generation_request.pk)
            generation_request.status = OrganizationGenerationRequest.Status.FAILED
            generation_request.completed_at = timezone.now()
            generation_request.error_message = str(exc)[:2000]
            generation_request.save(
                update_fields=("status", "completed_at", "error_message")
            )
            raise GenerationError(
                "No fue posible generar la estructura. Revisa la configuracion "
                "del proveedor o intenta nuevamente."
            ) from exc

    @staticmethod
    def _create_plan(
        generation_request: OrganizationGenerationRequest,
        proposal: OrganizationProposal,
    ) -> OrganizationalPlan:
        return OrganizationalPlan.objects.create(
            request=generation_request,
            company_name=proposal.company_name,
            company_summary=proposal.company_summary,
            assumptions=proposal.assumptions,
        )

    @staticmethod
    def _create_departments(
        plan: OrganizationalPlan,
        proposal: OrganizationProposal,
    ) -> dict[str, OrganizationalUnit]:
        pending = {department.code: department for department in proposal.departments}
        created: dict[str, OrganizationalUnit] = {}
        while pending:
            ready_codes = [
                code
                for code, department in pending.items()
                if department.parent_code is None or department.parent_code in created
            ]
            if not ready_codes:
                raise GenerationError("No se pudo resolver la jerarquia organizacional")
            for code in ready_codes:
                department = pending.pop(code)
                created[code] = OrganizationalUnit.objects.create(
                    plan=plan,
                    code=department.code,
                    name=department.name,
                    description=department.description,
                    parent=created.get(department.parent_code),
                )
        return created

    @staticmethod
    def _create_vacancies(
        plan: OrganizationalPlan,
        departments: dict[str, OrganizationalUnit],
        proposal: OrganizationProposal,
    ) -> None:
        for data in proposal.vacancies:
            vacancy = (
                VacancyBuilder()
                .for_plan(plan)
                .in_department(departments[data.department_code])
                .with_name(data.name)
                .with_positions(data.available_positions)
                .with_salary(
                    data.salary_min,
                    data.salary_max,
                    data.currency,
                    data.salary_period,
                )
                .with_description(data.description)
                .requiring(data.required_knowledge)
                .reporting_to(data.reports_to)
                .build()
            )
            vacancy.save()


class CalculatePlanMetricsService:
    """Calculate reusable plan metrics outside presentation classes."""

    def execute(self, plan: OrganizationalPlan) -> PlanMetricsDTO:
        units = tuple(plan.units.all())
        vacancies = tuple(plan.vacancies.all())
        return PlanMetricsDTO(
            department_count=len(units),
            vacancy_count=len(vacancies),
            total_positions=sum(vacancy.available_positions for vacancy in vacancies),
        )


@dataclass(frozen=True, slots=True)
class PlanDashboard:
    """Read model consumed by the server-rendered plan detail page."""

    root_units: tuple[OrganizationalUnit, ...]
    metrics: PlanMetricsDTO


class GetPlanDashboardService:
    """Prepare all plan-detail data that would otherwise be calculated in a view."""

    def __init__(
        self,
        metrics_service: CalculatePlanMetricsService | None = None,
    ) -> None:
        self._metrics_service = metrics_service or CalculatePlanMetricsService()

    def execute(self, plan: OrganizationalPlan) -> PlanDashboard:
        units = tuple(plan.units.all())
        return PlanDashboard(
            root_units=tuple(unit for unit in units if unit.parent_id is None),
            metrics=self._metrics_service.execute(plan),
        )


class ListOrganizationalPlansService:
    """Return an optimized lazy collection for database-backed pagination."""

    def __init__(self, plan_model: type[OrganizationalPlan] = OrganizationalPlan) -> None:
        self._plan_model = plan_model

    def execute(self) -> QuerySet[OrganizationalPlan]:
        return self._plan_model.objects.select_related("request").all()


class GetOrganizationalPlanService:
    """Load one complete plan and assemble its API/read-model DTO."""

    def __init__(
        self,
        plan_model: type[OrganizationalPlan] = OrganizationalPlan,
        unit_model: type[OrganizationalUnit] = OrganizationalUnit,
        vacancy_model: type[Vacancy] = Vacancy,
        metrics_service: CalculatePlanMetricsService | None = None,
    ) -> None:
        self._plan_model = plan_model
        self._unit_model = unit_model
        self._vacancy_model = vacancy_model
        self._metrics_service = metrics_service or CalculatePlanMetricsService()

    def execute(self, plan_id: int) -> PlanDetailDTO:
        queryset = self._plan_model.objects.select_related("request").prefetch_related(
            Prefetch("units", queryset=self._unit_model.objects.order_by("name")),
            Prefetch(
                "vacancies",
                queryset=self._vacancy_model.objects.select_related("department").order_by(
                    "department__name", "name"
                ),
            ),
        )
        try:
            plan = queryset.get(pk=plan_id)
        except self._plan_model.DoesNotExist as exc:
            raise ResourceNotFoundError(
                f"No existe un plan organizacional con id {plan_id}.",
                code="plan_not_found",
            ) from exc

        units = tuple(
            OrganizationalUnitDTO(
                id=unit.pk,
                code=unit.code,
                name=unit.name,
                description=unit.description,
                parent_id=unit.parent_id,
            )
            for unit in plan.units.all()
        )
        vacancies = tuple(_vacancy_to_dto(vacancy) for vacancy in plan.vacancies.all())

        return PlanDetailDTO(
            id=plan.pk,
            request_id=plan.request_id,
            company_name=plan.company_name,
            company_summary=plan.company_summary,
            assumptions=tuple(plan.assumptions),
            review_status=plan.review_status,
            generation_status=plan.request.status,
            provider_name=plan.request.provider_name,
            created_at=plan.created_at,
            metrics=self._metrics_service.execute(plan),
            units=units,
            vacancies=vacancies,
        )


class CreateVacancyService:
    """Create a vacancy through the domain Builder and enforce conflict semantics."""

    def __init__(
        self,
        plan_model: type[OrganizationalPlan] = OrganizationalPlan,
        unit_model: type[OrganizationalUnit] = OrganizationalUnit,
        vacancy_model: type[Vacancy] = Vacancy,
        builder_factory: Callable[[], VacancyBuilder] = VacancyBuilder,
    ) -> None:
        self._plan_model = plan_model
        self._unit_model = unit_model
        self._vacancy_model = vacancy_model
        self._builder_factory = builder_factory

    def execute(self, plan_id: int, command: CreateVacancyCommand) -> VacancyDTO:
        try:
            plan = self._plan_model.objects.get(pk=plan_id)
        except self._plan_model.DoesNotExist as exc:
            raise ResourceNotFoundError(
                f"No existe un plan organizacional con id {plan_id}.",
                code="plan_not_found",
            ) from exc

        try:
            department = self._unit_model.objects.get(pk=command.department_id, plan=plan)
        except self._unit_model.DoesNotExist as exc:
            raise ResourceNotFoundError(
                "El departamento indicado no existe dentro del plan.",
                code="department_not_found",
            ) from exc

        normalized_name = " ".join((command.name or "").split())
        duplicate_exists = normalized_name and self._vacancy_model.objects.filter(
            plan=plan,
            department=department,
            name__iexact=normalized_name,
        ).exists()
        if duplicate_exists:
            raise ResourceConflictError(
                "Ya existe una vacante con ese nombre en el departamento.",
                code="vacancy_already_exists",
            )

        vacancy = (
            self._builder_factory()
            .for_plan(plan)
            .in_department(department)
            .with_name(command.name)
            .with_positions(command.available_positions)
            .with_salary(
                command.salary_min,
                command.salary_max,
                command.currency,
                command.salary_period,
            )
            .with_description(command.description)
            .requiring(list(command.required_knowledge))
            .reporting_to(command.reports_to)
            .build()
        )
        try:
            with transaction.atomic():
                vacancy.save()
        except IntegrityError as exc:
            raise ResourceConflictError(
                "La vacante entra en conflicto con un registro existente.",
                code="vacancy_already_exists",
            ) from exc
        return _vacancy_to_dto(vacancy)


class GetVacancyService:
    """Load a vacancy within its parent plan and return the public read model."""

    def __init__(self, vacancy_model: type[Vacancy] = Vacancy) -> None:
        self._vacancy_model = vacancy_model

    def execute(self, plan_id: int, vacancy_id: int) -> VacancyDTO:
        try:
            vacancy = self._vacancy_model.objects.select_related("department").get(
                pk=vacancy_id,
                plan_id=plan_id,
            )
        except self._vacancy_model.DoesNotExist as exc:
            raise ResourceNotFoundError(
                "La vacante indicada no existe dentro del plan.",
                code="vacancy_not_found",
            ) from exc
        return _vacancy_to_dto(vacancy)


def _vacancy_to_dto(vacancy: Vacancy) -> VacancyDTO:
    return VacancyDTO(
        id=vacancy.pk,
        department_id=vacancy.department_id,
        department_name=vacancy.department.name,
        name=vacancy.name,
        available_positions=vacancy.available_positions,
        salary_min=vacancy.salary_min,
        salary_max=vacancy.salary_max,
        currency=vacancy.currency,
        salary_period=vacancy.salary_period,
        description=vacancy.description,
        required_knowledge=tuple(vacancy.required_knowledge),
        reports_to=vacancy.reports_to,
        status=vacancy.status,
        created_at=vacancy.created_at,
    )
