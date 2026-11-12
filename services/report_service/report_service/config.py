"""Environment-backed configuration shared by the report API and the Celery worker."""

from __future__ import annotations

import os


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SERVICE_NAME = "report-service"
    SERVICE_VERSION = "2.0.0"

    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
    CELERY_TASK_ALWAYS_EAGER = _env_bool("CELERY_TASK_ALWAYS_EAGER", False)
    REPORT_RESULT_TTL_SECONDS = int(os.environ.get("REPORT_RESULT_TTL_SECONDS", 24 * 3600))

    # Redis database used for notifications and the report registry ("memory://" for local runs).
    NOTIFICATION_STORE_URL = os.environ.get("NOTIFICATION_STORE_URL", "redis://localhost:6379/2")
    MAX_NOTIFICATIONS = int(os.environ.get("MAX_NOTIFICATIONS", 100))

    PLAN_SERVICE_URL = os.environ.get("PLAN_SERVICE_URL", "http://localhost:5001").rstrip("/")
    INTEGRATION_SERVICE_URL = os.environ.get("INTEGRATION_SERVICE_URL", "").rstrip("/")
    HTTP_TIMEOUT_SECONDS = float(os.environ.get("HTTP_TIMEOUT_SECONDS", 5))

    # Optional e-mail notifications. Without SMTP_HOST notifications are only logged and stored.
    SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
    SMTP_USER = os.environ.get("SMTP_USER", "").strip()
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_USE_TLS = _env_bool("SMTP_USE_TLS", True)
    NOTIFY_EMAIL_FROM = os.environ.get("NOTIFY_EMAIL_FROM", "joblab@localhost")
    NOTIFY_EMAIL_TO = os.environ.get("NOTIFY_EMAIL_TO", "").strip()

    BABEL_DEFAULT_LOCALE = "es"
    SUPPORTED_LOCALES = ("es", "en")
    MAX_CONTENT_LENGTH = 16 * 1024
