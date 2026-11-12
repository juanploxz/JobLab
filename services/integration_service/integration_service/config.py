"""Environment-backed configuration for the integration microservice."""

from __future__ import annotations

import os


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


class Config:
    SERVICE_NAME = "integration-service"
    SERVICE_VERSION = "2.0.0"

    # Third-party exchange-rate API (consumed through the Adapter pattern).
    EXCHANGE_PROVIDERS = os.environ.get("EXCHANGE_PROVIDERS", "open_er_api,frankfurter,static")
    OPEN_ER_API_URL = os.environ.get("OPEN_ER_API_URL", "https://open.er-api.com/v6/latest")
    FRANKFURTER_API_URL = os.environ.get("FRANKFURTER_API_URL", "https://api.frankfurter.dev/v1/latest")
    RATES_CACHE_TTL_SECONDS = _env_float("RATES_CACHE_TTL_SECONDS", 3600)

    # Allied team service (consumed through a configurable Adapter).
    ALLY_SERVICE_NAME = os.environ.get("ALLY_SERVICE_NAME", "Equipo aliado")
    ALLY_SERVICE_URL = os.environ.get("ALLY_SERVICE_URL", "").strip()
    ALLY_ITEMS_PATH = os.environ.get("ALLY_ITEMS_PATH", "").strip()
    ALLY_FIELD_TITLE = os.environ.get("ALLY_FIELD_TITLE", "name,title,nombre,titulo")
    ALLY_FIELD_SUBTITLE = os.environ.get(
        "ALLY_FIELD_SUBTITLE", "category,company,empresa,categoria,type,tipo"
    )
    ALLY_FIELD_DESCRIPTION = os.environ.get(
        "ALLY_FIELD_DESCRIPTION", "description,descripcion,summary,resumen,detail"
    )
    ALLY_FIELD_URL = os.environ.get("ALLY_FIELD_URL", "url,link,enlace")
    ALLY_API_KEY = os.environ.get("ALLY_API_KEY", "").strip()
    ALLY_CACHE_TTL_SECONDS = _env_float("ALLY_CACHE_TTL_SECONDS", 120)

    # Resilience settings shared by every outbound HTTP adapter.
    HTTP_TIMEOUT_SECONDS = _env_float("HTTP_TIMEOUT_SECONDS", 4)
    CIRCUIT_FAILURE_THRESHOLD = int(_env_float("CIRCUIT_FAILURE_THRESHOLD", 3))
    CIRCUIT_RESET_SECONDS = _env_float("CIRCUIT_RESET_SECONDS", 30)

    BABEL_DEFAULT_LOCALE = "es"
    SUPPORTED_LOCALES = ("es", "en")
    MAX_CONTENT_LENGTH = 64 * 1024
    MAX_BATCH_ITEMS = 200
