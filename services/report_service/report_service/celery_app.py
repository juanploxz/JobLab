"""Celery application (Redis broker) shared by the report API and the worker.

Worker command:
    celery -A report_service.celery_app worker -Q reports,notifications --loglevel=INFO
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from celery import Celery

from report_service.config import Config

celery = Celery("report_service", include=["report_service.tasks"])

# Settings shared with the tasks (service URLs, SMTP, store URL).
settings: dict[str, Any] = {key: getattr(Config, key) for key in dir(Config) if key.isupper()}


def configure(overrides: Mapping[str, Any] | None = None) -> Celery:
    if overrides:
        settings.update(overrides)
    celery.conf.update(
        broker_url=settings["CELERY_BROKER_URL"],
        result_backend=settings["CELERY_RESULT_BACKEND"],
        task_always_eager=settings["CELERY_TASK_ALWAYS_EAGER"],
        task_store_eager_result=True,
        task_eager_propagates=False,
        result_expires=settings["REPORT_RESULT_TTL_SECONDS"],
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_track_started=True,
        broker_connection_retry_on_startup=True,
        broker_transport_options={"socket_timeout": 3, "socket_connect_timeout": 3},
        task_routes={
            "reports.*": {"queue": "reports"},
            "notifications.*": {"queue": "notifications"},
        },
        timezone="America/Bogota",
        enable_utc=True,
    )
    return celery


configure()
