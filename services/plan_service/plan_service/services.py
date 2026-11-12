"""Application services (Service Layer) migrated from the Django monolith."""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from plan_service.domain.builders import VacancyBuilder
from plan_service.domain.exceptions import (
    DomainValidationError,
    GenerationError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from plan_service.domain.ports import EventPublisher, OrganizationGenerator
from plan_service.domain.schemas import OrganizationProposal
from plan_service.domain.validators import normalize_spaces, validate_company_description
from plan_service.dtos import (
    CreateVacancyCommand,
    PageDTO,
    PlanDetailDTO,
    PlanMetricsDTO,
    PlanSummaryDTO,
    UnitDTO,
    VacancyDTO,
)
from plan_service.i18n import _
from plan_service.models import GenerationRequest, Plan, Unit, Vacancy

logger = logging.getLogger(__name__)


class CalculatePlanMetricsService:
    def execute(self, plan: Plan) -> PlanMetricsDTO:
        return PlanMetricsDTO(
            department_count=len(plan.units),
            vacancy_count=len(plan.vacancies),
            total_positions=sum(vacancy.available_positions for vacancy in plan.vacancies),
        )


class GenerateOrganizationService:
    """Generate, validate and persist a complete plan, then publish ``plan.created``."""

    def __init__(
        self,
        ai_provider: OrganizationGenerator,
        session: Session,
        event_publisher: EventPublisher,
        builder_factory: Callable[[], VacancyBuilder] = VacancyBuilder,
        metrics_service: CalculatePlanMetricsService | None = None,
    ) -> None:
        self._provider = ai_provider
        self._session = session
        self._events = event_publisher
        self._builder_factory = builder_factory
        self._metrics = metrics_service or CalculatePlanMetricsService()

    def execute(self, company_description: str) -> Plan:
        description = validate_company_description(company_description)
        generation_request = GenerationRequest(
            company_description=description,
            provider_name=self._provider.name,
            status=GenerationRequest.PROCESSING,
        )
        self._session.add(generation_request)
        self._session.commit()
        request_id = generation_request.id

        try:
            proposal = OrganizationProposal.model_validate(self._provider.generate(description))
            plan = Plan(
                request=generation_request,
                company_name=proposal.company_name,
                company_summary=proposal.company_summary,
                assumptions=list(proposal.assumptions),
            )
            self._session.add(plan)
            units = self._create_units(plan, proposal)
            for vacancy in self._build_vacancies(plan, units, proposal):
                self._session.add(vacancy)
            generation_request.status = GenerationRequest.COMPLETED
            generation_request.completed_at = datetime.now(UTC)
            generation_request.error_message = ""
            self._session.commit()
        except Exception as exc:
            logger.exception("Organization generation failed for request %s", request_id)
            self._session.rollback()
            failed = self._session.get(GenerationRequest, request_id)
            if failed is not None:
                failed.status = GenerationRequest.FAILED
                failed.completed_at = datetime.now(UTC)
                failed.error_message = str(exc)[:2000]
                self._session.commit()
            raise GenerationError(
                _("No fue posible generar la estructura. Intenta nuevamente más tarde.")
            ) from exc

        metrics = self._metrics.execute(plan)
        self._events.publish(
            "plan.created",
            {
                "plan_id": plan.id,
                "company_name": plan.company_name,
                "department_count": metrics.department_count,
                "vacancy_count": metrics.vacancy_count,
                "total_positions": metrics.total_positions,
                "provider_name": generation_request.provider_name,
            },
        )
        return plan

    def _create_units(self, plan: Plan, proposal: OrganizationProposal) -> dict[str, Unit]:
        pending = {department.code: department for department in proposal.departments}
        created: dict[str, Unit] = {}
        while pending:
            ready = [
                code
                for code, department in pending.items()
                if department.parent_code is None or department.parent_code in created
            ]
            if not ready:
                raise GenerationError("unresolvable organizational hierarchy")
            for code in ready:
                department = pending.pop(code)
                unit = Unit(
                    plan=plan,
                    code=department.code,
                    name=department.name,
                    description=department.description,
                    parent=created.get(department.parent_code),
                )
                self._session.add(unit)
                created[code] = unit
        return created

    def _build_vacancies(
        self, plan: Plan, units: dict[str, Unit], proposal: OrganizationProposal
    ) -> list[Vacancy]:
        return [
            self._builder_factory()
            .for_plan(plan)
            .in_department(units[data.department_code])
            .with_name(data.name)
            .with_positions(data.available_positions)
            .with_salary(data.salary_min, data.salary_max, data.currency, data.salary_period)
            .with_description(data.description)
            .requiring(list(data.required_knowledge))
            .reporting_to(data.reports_to)
            .build()
            for data in proposal.vacancies
        ]


class PreviewProposalService:
    """Strangler step from Taller 02: return a proposal without persisting it."""

    def __init__(self, ai_provider: OrganizationGenerator) -> None:
        self._provider = ai_provider

    def execute(self, company_description: str) -> tuple[str, OrganizationProposal]:
        description = validate_company_description(company_description)
        try:
            proposal = OrganizationProposal.model_validate(self._provider.generate(description))
        except DomainValidationError:
            raise
        except Exception as exc:
            logger.exception("Preview generation failed")
            raise GenerationError(
                _("No fue posible generar la estructura. Intenta nuevamente más tarde.")
            ) from exc
        return description, proposal


class ListPlansService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def execute(self, page: int, page_size: int) -> PageDTO:
        total = self._session.scalar(select(func.count(Plan.id))) or 0
        if page < 1 or (page > 1 and (page - 1) * page_size >= total):
            raise ResourceNotFoundError(_("Página inválida."), code="page_not_found")
        plans = self._session.scalars(
            select(Plan)
            .options(joinedload(Plan.request))
            .order_by(Plan.created_at.desc(), Plan.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        items = tuple(
            PlanSummaryDTO(
                id=plan.id,
                company_name=plan.company_name,
                company_summary=plan.company_summary,
                review_status=plan.review_status,
                generation_status=plan.request.status,
                provider_name=plan.request.provider_name,
                created_at=plan.created_at,
            )
            for plan in plans
        )
        return PageDTO(items=items, total=total, page=page, page_size=page_size)


def _plan_not_found(plan_id: int) -> ResourceNotFoundError:
    return ResourceNotFoundError(
        _("No existe un plan organizacional con id %(plan_id)s.", plan_id=plan_id),
        code="plan_not_found",
    )


class GetPlanService:
    def __init__(
        self, session: Session, metrics_service: CalculatePlanMetricsService | None = None
    ) -> None:
        self._session = session
        self._metrics = metrics_service or CalculatePlanMetricsService()

    def execute(self, plan_id: int) -> PlanDetailDTO:
        plan = self._session.scalar(
            select(Plan)
            .where(Plan.id == plan_id)
            .options(
                joinedload(Plan.request),
                selectinload(Plan.units),
                selectinload(Plan.vacancies).joinedload(Vacancy.department),
            )
        )
        if plan is None:
            raise _plan_not_found(plan_id)
        vacancies = sorted(plan.vacancies, key=lambda v: (v.department.name, v.name))
        return PlanDetailDTO(
            id=plan.id,
            request_id=plan.request_id,
            company_name=plan.company_name,
            company_summary=plan.company_summary,
            assumptions=tuple(plan.assumptions or ()),
            review_status=plan.review_status,
            generation_status=plan.request.status,
            provider_name=plan.request.provider_name,
            created_at=plan.created_at,
            metrics=self._metrics.execute(plan),
            units=tuple(
                UnitDTO(
                    id=unit.id,
                    code=unit.code,
                    name=unit.name,
                    description=unit.description,
                    parent_id=unit.parent_id,
                )
                for unit in plan.units
            ),
            vacancies=tuple(vacancy_to_dto(vacancy) for vacancy in vacancies),
        )


class CreateVacancyService:
    def __init__(
        self,
        session: Session,
        event_publisher: EventPublisher,
        builder_factory: Callable[[], VacancyBuilder] = VacancyBuilder,
    ) -> None:
        self._session = session
        self._events = event_publisher
        self._builder_factory = builder_factory

    def execute(self, plan_id: int, command: CreateVacancyCommand) -> VacancyDTO:
        plan = self._session.get(Plan, plan_id)
        if plan is None:
            raise _plan_not_found(plan_id)
        department = self._session.scalar(
            select(Unit).where(Unit.id == command.department_id, Unit.plan_id == plan.id)
        )
        if department is None:
            raise ResourceNotFoundError(
                _("El departamento indicado no existe dentro del plan."),
                code="department_not_found",
            )

        name_key = normalize_spaces(command.name if isinstance(command.name, str) else "").casefold()
        duplicate = name_key and self._session.scalar(
            select(func.count(Vacancy.id)).where(
                Vacancy.plan_id == plan.id,
                Vacancy.department_id == department.id,
                Vacancy.name_key == name_key,
            )
        )
        if duplicate:
            raise ResourceConflictError(
                _("Ya existe una vacante con ese nombre en el departamento."),
                code="vacancy_already_exists",
            )

        vacancy = (
            self._builder_factory()
            .for_plan(plan)
            .in_department(department)
            .with_name(command.name)
            .with_positions(command.available_positions)
            .with_salary(
                command.salary_min, command.salary_max, command.currency, command.salary_period
            )
            .with_description(command.description)
            .requiring(list(command.required_knowledge))
            .reporting_to(command.reports_to)
            .build()
        )
        self._session.add(vacancy)
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ResourceConflictError(
                _("La vacante entra en conflicto con un registro existente."),
                code="vacancy_already_exists",
            ) from exc

        self._events.publish(
            "vacancy.created",
            {
                "plan_id": plan.id,
                "vacancy_id": vacancy.id,
                "company_name": plan.company_name,
                "vacancy_name": vacancy.name,
                "available_positions": vacancy.available_positions,
            },
        )
        return vacancy_to_dto(vacancy)


class GetVacancyService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def execute(self, plan_id: int, vacancy_id: int) -> VacancyDTO:
        vacancy = self._session.scalar(
            select(Vacancy)
            .where(Vacancy.id == vacancy_id, Vacancy.plan_id == plan_id)
            .options(joinedload(Vacancy.department))
        )
        if vacancy is None:
            raise ResourceNotFoundError(
                _("La vacante indicada no existe dentro del plan."),
                code="vacancy_not_found",
            )
        return vacancy_to_dto(vacancy)


class PublicSummaryService:
    """Read model exposed to the allied team (service to provide)."""

    def __init__(self, session: Session, skills_sample: int = 500) -> None:
        self._session = session
        self._skills_sample = skills_sample

    def execute(self, latest_limit: int = 10) -> dict[str, Any]:
        totals = {
            "plans": self._session.scalar(select(func.count(Plan.id))) or 0,
            "departments": self._session.scalar(select(func.count(Unit.id))) or 0,
            "vacancies": self._session.scalar(select(func.count(Vacancy.id))) or 0,
            "positions": int(
                self._session.scalar(select(func.coalesce(func.sum(Vacancy.available_positions), 0)))
                or 0
            ),
        }
        recent = self._session.scalars(
            select(Vacancy)
            .options(joinedload(Vacancy.department), joinedload(Vacancy.plan))
            .order_by(Vacancy.created_at.desc(), Vacancy.id.desc())
            .limit(self._skills_sample)
        ).all()
        skills = Counter(
            skill for vacancy in recent for skill in (vacancy.required_knowledge or [])
        )
        return {
            "totals": totals,
            "top_skills": [
                {"name": name, "vacancies": count} for name, count in skills.most_common(10)
            ],
            "latest_vacancies": [
                {
                    "plan_id": vacancy.plan_id,
                    "company_name": vacancy.plan.company_name,
                    "vacancy_id": vacancy.id,
                    "name": vacancy.name,
                    "department": vacancy.department.name,
                    "available_positions": vacancy.available_positions,
                    "salary_min": vacancy.salary_min,
                    "salary_max": vacancy.salary_max,
                    "currency": vacancy.currency,
                    "salary_period": vacancy.salary_period,
                    "required_knowledge": list(vacancy.required_knowledge or []),
                    "status": vacancy.status,
                }
                for vacancy in recent[:latest_limit]
            ],
        }


def vacancy_to_dto(vacancy: Vacancy) -> VacancyDTO:
    return VacancyDTO(
        id=vacancy.id,
        plan_id=vacancy.plan_id,
        department_id=vacancy.department_id,
        department_name=vacancy.department.name,
        name=vacancy.name,
        available_positions=vacancy.available_positions,
        salary_min=vacancy.salary_min,
        salary_max=vacancy.salary_max,
        currency=vacancy.currency,
        salary_period=vacancy.salary_period,
        description=vacancy.description,
        required_knowledge=tuple(vacancy.required_knowledge or ()),
        reports_to=vacancy.reports_to or "",
        status=vacancy.status,
        created_at=vacancy.created_at,
    )
