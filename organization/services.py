import logging

from django.db import transaction
from django.utils import timezone

from organization.domain.builders import VacancyBuilder
from organization.domain.exceptions import GenerationError
from organization.domain.ports import OrganizationGenerator
from organization.domain.schemas import OrganizationProposal
from organization.domain.validators import validate_company_description
from organization.models import (
    OrganizationalPlan,
    OrganizationalUnit,
    OrganizationGenerationRequest,
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
