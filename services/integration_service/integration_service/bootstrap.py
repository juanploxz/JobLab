"""Composition root: build the adapter chains once per process from configuration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from integration_service.adapters import (
    CachedAllyCatalog,
    CachedRateProvider,
    FallbackRateProvider,
    FrankfurterAdapter,
    HttpAllyCatalogAdapter,
    OpenErApiAdapter,
    StaticRatesAdapter,
    UnconfiguredAllyCatalog,
)
from integration_service.domain import AllyCatalogProvider, ExchangeRateProvider
from integration_service.resilience import CircuitBreaker, build_http_session


def _csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _http_kwargs(config: Mapping[str, Any], name: str, session) -> dict[str, Any]:
    return {
        "session": session,
        "timeout": config["HTTP_TIMEOUT_SECONDS"],
        "breaker": CircuitBreaker(
            name,
            failure_threshold=config["CIRCUIT_FAILURE_THRESHOLD"],
            reset_seconds=config["CIRCUIT_RESET_SECONDS"],
        ),
    }


def build_exchange_provider(config: Mapping[str, Any], session=None) -> ExchangeRateProvider:
    session = session or build_http_session()
    builders = {
        "open_er_api": lambda: OpenErApiAdapter(
            config["OPEN_ER_API_URL"], **_http_kwargs(config, "open_er_api", session)
        ),
        "frankfurter": lambda: FrankfurterAdapter(
            config["FRANKFURTER_API_URL"], **_http_kwargs(config, "frankfurter", session)
        ),
        "static": StaticRatesAdapter,
    }
    names = [name for name in _csv(config["EXCHANGE_PROVIDERS"]) if name in builders] or ["static"]
    chain = FallbackRateProvider([builders[name]() for name in names])
    return CachedRateProvider(chain, ttl_seconds=config["RATES_CACHE_TTL_SECONDS"])


def build_ally_catalog(config: Mapping[str, Any], session=None) -> AllyCatalogProvider:
    if not config["ALLY_SERVICE_URL"]:
        return UnconfiguredAllyCatalog()
    adapter = HttpAllyCatalogAdapter(
        ally_name=config["ALLY_SERVICE_NAME"],
        url=config["ALLY_SERVICE_URL"],
        items_path=config["ALLY_ITEMS_PATH"],
        title_fields=_csv(config["ALLY_FIELD_TITLE"]),
        subtitle_fields=_csv(config["ALLY_FIELD_SUBTITLE"]),
        description_fields=_csv(config["ALLY_FIELD_DESCRIPTION"]),
        url_fields=_csv(config["ALLY_FIELD_URL"]),
        api_key=config["ALLY_API_KEY"],
        **_http_kwargs(config, "ally", session or build_http_session()),
    )
    return CachedAllyCatalog(adapter, ttl_seconds=config["ALLY_CACHE_TTL_SECONDS"])
