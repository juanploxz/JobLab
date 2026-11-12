"""Event publishers that decouple plan creation from background processing."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Integration-event name -> Celery task consumed by the report/notification worker.
EVENT_TASKS = {
    "plan.created": ("notifications.plan_created", "notifications"),
    "vacancy.created": ("notifications.vacancy_created", "notifications"),
}


class NullEventPublisher:
    """Used when no broker is configured: the event is only logged."""

    def publish(self, event_name: str, payload: dict[str, Any]) -> None:
        logger.info("Event %s not published (no broker configured): %s", event_name, payload)


class InMemoryEventPublisher:
    """Test double that records published events."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def publish(self, event_name: str, payload: dict[str, Any]) -> None:
        self.events.append((event_name, payload))


class CeleryEventPublisher:
    """Send integration events to Redis through Celery without importing the worker code."""

    def __init__(self, broker_url: str, celery_app=None) -> None:
        if celery_app is None:
            from celery import Celery

            celery_app = Celery("plan_service_events", broker=broker_url)
            celery_app.conf.broker_connection_retry_on_startup = True
        self._celery = celery_app

    def publish(self, event_name: str, payload: dict[str, Any]) -> None:
        task_name, queue = EVENT_TASKS[event_name]
        try:
            self._celery.send_task(
                task_name,
                kwargs={"payload": payload},
                queue=queue,
                retry=True,
                retry_policy={
                    "max_retries": 2,
                    "interval_start": 0,
                    "interval_step": 0.5,
                    "interval_max": 1,
                },
            )
        except Exception:  # noqa: BLE001 - the business transaction already succeeded
            logger.warning("Event %s could not reach the broker", event_name, exc_info=True)


def build_event_publisher(broker_url: str):
    return CeleryEventPublisher(broker_url) if broker_url else NullEventPublisher()
