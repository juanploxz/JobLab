"""Composition root: wire adapters into application services per request."""

from __future__ import annotations

from flask import current_app

from plan_service.extensions import db
from plan_service.infra.ai.factory import AIProviderFactory
from plan_service.services import (
    CreateVacancyService,
    GenerateOrganizationService,
    GetPlanService,
    GetVacancyService,
    ListPlansService,
    PreviewProposalService,
    PublicSummaryService,
)

EVENT_PUBLISHER_KEY = "joblab.event_publisher"


def event_publisher():
    return current_app.extensions[EVENT_PUBLISHER_KEY]


def ai_provider():
    return AIProviderFactory.create(current_app.config)


def generation_service() -> GenerateOrganizationService:
    return GenerateOrganizationService(
        ai_provider=ai_provider(), session=db.session, event_publisher=event_publisher()
    )


def preview_service() -> PreviewProposalService:
    return PreviewProposalService(ai_provider=ai_provider())


def list_plans_service() -> ListPlansService:
    return ListPlansService(session=db.session)


def get_plan_service() -> GetPlanService:
    return GetPlanService(session=db.session)


def create_vacancy_service() -> CreateVacancyService:
    return CreateVacancyService(session=db.session, event_publisher=event_publisher())


def get_vacancy_service() -> GetVacancyService:
    return GetVacancyService(session=db.session)


def public_summary_service() -> PublicSummaryService:
    return PublicSummaryService(session=db.session)
