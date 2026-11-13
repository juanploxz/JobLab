"""Environment-backed configuration for the plan microservice."""

from __future__ import annotations

import os


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SERVICE_NAME = "plan-service"
    SERVICE_VERSION = "2.0.0"

    SQLALCHEMY_DATABASE_URI = os.environ.get("PLAN_DATABASE_URL", "sqlite:///plan_service.db")
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    AUTO_CREATE_SCHEMA = _env_bool("PLAN_AUTO_CREATE_SCHEMA", True)

    AI_PROVIDER = os.environ.get("AI_PROVIDER", "MOCK").strip().upper()
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite").strip()
    GEMINI_TIMEOUT_MS = int(os.environ.get("GEMINI_TIMEOUT_MS", "60000"))

    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "").strip()

    BABEL_DEFAULT_LOCALE = "es"
    SUPPORTED_LOCALES = ("es", "en")

    MAX_CONTENT_LENGTH = 64 * 1024
    DEFAULT_PAGE_SIZE = 10
    MAX_PAGE_SIZE = 50
