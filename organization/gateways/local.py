"""Legacy adapter: runs the original in-process Service Layer (rollback path of the strangler)."""

from __future__ import annotations

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.utils.translation import gettext as _

from organization.bootstrap import build_generation_service
from organization.domain.exceptions import ResourceNotFoundError
from organization.dtos import PlanDetailDTO, PlanPageDTO, PlanSummaryDTO
from organization.services import GetOrganizationalPlanService, ListOrganizationalPlansService


class LocalPlanGateway:
    name = "django-monolith"

    def generate_plan(self, company_description: str) -> int:
        return build_generation_service().execute(company_description).pk

    def get_plan(self, plan_id: int) -> PlanDetailDTO:
        return GetOrganizationalPlanService().execute(plan_id)

    def list_plans(self, page: int, page_size: int) -> PlanPageDTO:
        paginator = Paginator(ListOrganizationalPlansService().execute(), page_size)
        try:
            current = paginator.page(page)
        except (EmptyPage, PageNotAnInteger) as exc:
            raise ResourceNotFoundError(_("Página inválida."), code="page_not_found") from exc
        items = tuple(
            PlanSummaryDTO(
                id=plan.pk,
                company_name=plan.company_name,
                company_summary=plan.company_summary,
                review_status=plan.review_status,
                generation_status=plan.request.status,
                provider_name=plan.request.provider_name,
                created_at=plan.created_at,
            )
            for plan in current.object_list
        )
        return PlanPageDTO(items=items, count=paginator.count, page=current.number, page_size=page_size)
