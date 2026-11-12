"""Aggregated health of the ecosystem shown on the system-status page."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

import requests
from django.db import connection

from organization.gateways import factory

HEALTH_TIMEOUT_SECONDS = 2


@dataclass(frozen=True, slots=True)
class ServiceHealth:
    name: str
    configured: bool
    healthy: bool
    latency_ms: int | None
    details: dict


def _database() -> ServiceHealth:
    start = perf_counter()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        healthy = True
    except Exception:  # noqa: BLE001 - shown as unhealthy
        healthy = False
    return ServiceHealth(
        "django-db", True, healthy, int((perf_counter() - start) * 1000), {"vendor": connection.vendor}
    )


def _probe(name: str, url: str) -> ServiceHealth:
    """Plain probe (no retries, no circuit breaker) so monitoring never trips real traffic."""
    start = perf_counter()
    try:
        response = requests.get(f"{url.rstrip('/')}/health", timeout=HEALTH_TIMEOUT_SECONDS)
        body = response.json()
        healthy = response.status_code == 200
    except (requests.RequestException, ValueError):
        body, healthy = {}, False
    checks = body.get("checks", {}) if isinstance(body, dict) else {}
    return ServiceHealth(name, True, healthy, int((perf_counter() - start) * 1000), checks)


def collect_health() -> list[ServiceHealth]:
    results = [_database()]
    for name, url in factory.configured_services().items():
        results.append(_probe(name, url) if url else ServiceHealth(name, False, False, None, {}))
    return results
