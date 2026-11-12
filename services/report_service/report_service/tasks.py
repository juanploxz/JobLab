"""Background tasks executed by the Celery worker."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from report_service.celery_app import celery, settings
from report_service.clients import (
    PlanServiceClient,
    SalaryConversionClient,
    UpstreamUnavailable,
)
from report_service.i18n import translate
from report_service.notifiers import build_notifier
from report_service.reports import ReportRendererFactory
from report_service.stores import get_store

logger = logging.getLogger(__name__)


def _store():
    return get_store(settings["NOTIFICATION_STORE_URL"], settings["MAX_NOTIFICATIONS"])


@celery.task(
    bind=True,
    name="reports.generate_plan_report",
    autoretry_for=(UpstreamUnavailable,),
    retry_backoff=2,
    retry_backoff_max=30,
    retry_jitter=True,
    max_retries=3,
)
def generate_plan_report(self, plan_id: int, report_format: str = "csv", language: str = "es") -> dict[str, Any]:
    """Fetch the plan, enrich salaries with USD and render the requested format."""
    timeout = settings["HTTP_TIMEOUT_SECONDS"]
    # PlanNotFound is not in autoretry_for: the task fails at once with that exception type.
    plan = PlanServiceClient(settings["PLAN_SERVICE_URL"], timeout).get_plan(plan_id, language)
    usd = SalaryConversionClient(settings["INTEGRATION_SERVICE_URL"], timeout).to_usd(plan.get("vacancies", []))
    rendered = ReportRendererFactory.create(report_format).render(plan, usd, language)
    _store().add_notification(
        "report.ready",
        {"plan_id": plan_id, "company_name": plan["company_name"], "format": report_format, "task_id": self.request.id},
    )
    return {
        "plan_id": plan_id,
        "format": report_format,
        "filename": rendered.filename,
        "content_type": rendered.content_type,
        "content": rendered.content,
        "salary_conversion": bool(usd),
        "generated_at": datetime.now(UTC).isoformat(),
    }


def _notify(kind: str, payload: dict[str, Any], subject: str, body: str) -> dict[str, Any]:
    item = _store().add_notification(kind, payload)
    try:
        build_notifier(settings).send(subject, body)
        item["delivered"] = True
    except Exception:  # noqa: BLE001 - the notification stays in the log even if e-mail fails
        logger.warning("Notification channel failed for %s", kind, exc_info=True)
        item["delivered"] = False
    return item


@celery.task(name="notifications.plan_created", max_retries=0)
def plan_created(payload: dict[str, Any]) -> dict[str, Any]:
    subject = translate("es", "JobLab: nuevo plan organizacional")
    body = translate(
        "es",
        "Se generó el plan %(plan_id)s para %(company_name)s con %(vacancy_count)s vacantes "
        "y %(total_positions)s puestos sugeridos.",
        plan_id=payload.get("plan_id"),
        company_name=payload.get("company_name"),
        vacancy_count=payload.get("vacancy_count"),
        total_positions=payload.get("total_positions"),
    )
    return _notify("plan.created", payload, subject, body)


@celery.task(name="notifications.vacancy_created", max_retries=0)
def vacancy_created(payload: dict[str, Any]) -> dict[str, Any]:
    subject = translate("es", "JobLab: nueva vacante")
    body = translate(
        "es",
        "Se creó la vacante %(vacancy_name)s en el plan %(plan_id)s.",
        vacancy_name=payload.get("vacancy_name"),
        plan_id=payload.get("plan_id"),
    )
    return _notify("vacancy.created", payload, subject, body)
