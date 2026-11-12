"""Adapters (GoF Adapter pattern) that translate third-party APIs to the domain ports.

* ``OpenErApiAdapter``      -> open.er-api.com (ExchangeRate-API, no key)
* ``FrankfurterAdapter``    -> api.frankfurter.dev (European Central Bank rates)
* ``StaticRatesAdapter``    -> offline reference table used as last resort
* ``FallbackRateProvider``  -> tries several adapters in order (resilience)
* ``CachedRateProvider``    -> Decorator that keeps the last good table for a TTL
* ``HttpAllyCatalogAdapter``-> maps the allied team's JSON to ``AllyCatalog``
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import requests

from integration_service.domain import (
    AllyCatalog,
    AllyCatalogProvider,
    AllyItem,
    ExchangeRateProvider,
    IntegrationNotConfiguredError,
    ProviderUnavailableError,
    RateTable,
)
from integration_service.resilience import CircuitBreaker, CircuitOpenError

logger = logging.getLogger(__name__)


def _decimal_rates(raw: Mapping[str, Any]) -> dict[str, Decimal]:
    rates: dict[str, Decimal] = {}
    for code, value in raw.items():
        try:
            rate = Decimal(str(value))
        except (InvalidOperation, ValueError):
            continue
        if isinstance(code, str) and len(code) == 3 and rate.is_finite() and rate > 0:
            rates[code.upper()] = rate
    return rates


class _HttpJsonAdapter:
    def __init__(
        self,
        session: requests.Session,
        timeout: float,
        breaker: CircuitBreaker,
    ) -> None:
        self._session = session
        self._timeout = timeout
        self._breaker = breaker

    def _get_json(self, url: str, **kwargs: Any) -> Any:
        def operation() -> Any:
            response = self._session.get(url, timeout=self._timeout, **kwargs)
            response.raise_for_status()
            return response.json()

        try:
            return self._breaker.call(operation)
        except CircuitOpenError as exc:
            raise ProviderUnavailableError(str(exc)) from exc
        except (requests.RequestException, ValueError) as exc:
            raise ProviderUnavailableError(f"{url}: {exc}") from exc


class OpenErApiAdapter(_HttpJsonAdapter):
    """Adapter for https://open.er-api.com/v6/latest/{BASE}."""

    name = "open.er-api.com"

    def __init__(self, base_url: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._base_url = base_url.rstrip("/")

    def latest(self, base: str = "USD") -> RateTable:
        payload = self._get_json(f"{self._base_url}/{base.upper()}")
        if not isinstance(payload, dict) or payload.get("result") != "success":
            raise ProviderUnavailableError("open.er-api.com returned an unexpected payload")
        rates = _decimal_rates(payload.get("rates") or {})
        if not rates:
            raise ProviderUnavailableError("open.er-api.com returned no rates")
        updated = payload.get("time_last_update_unix")
        fetched_at = datetime.fromtimestamp(updated, UTC) if isinstance(updated, int) else datetime.now(UTC)
        return RateTable(
            base=str(payload.get("base_code", base)).upper(),
            rates=rates,
            provider=self.name,
            fetched_at=fetched_at,
        )


class FrankfurterAdapter(_HttpJsonAdapter):
    """Adapter for https://api.frankfurter.dev/v1/latest?base={BASE} (no COP support)."""

    name = "frankfurter.dev"

    def __init__(self, base_url: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._base_url = base_url

    def latest(self, base: str = "USD") -> RateTable:
        payload = self._get_json(self._base_url, params={"base": base.upper()})
        if not isinstance(payload, dict) or "rates" not in payload:
            raise ProviderUnavailableError("frankfurter returned an unexpected payload")
        rates = _decimal_rates(payload["rates"])
        if not rates:
            raise ProviderUnavailableError("frankfurter returned no rates")
        return RateTable(
            base=str(payload.get("base", base)).upper(),
            rates=rates,
            provider=self.name,
            fetched_at=datetime.now(UTC),
        )


class StaticRatesAdapter:
    """Offline reference rates (USD base). Always marked as stale."""

    name = "static-reference"
    REFERENCE_RATES = {
        "COP": Decimal("3900"),
        "EUR": Decimal("0.92"),
        "MXN": Decimal("18.5"),
        "USD": Decimal("1"),
    }

    def latest(self, base: str = "USD") -> RateTable:
        table = RateTable(
            base="USD",
            rates=dict(self.REFERENCE_RATES),
            provider=self.name,
            fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
            stale=True,
        )
        return table if base.upper() == "USD" else table.rebased(base)


class FallbackRateProvider:
    """Try each provider in order and return the first table that contains the required currencies."""

    def __init__(
        self,
        providers: Sequence[ExchangeRateProvider],
        required_currencies: Iterable[str] = ("COP", "USD", "EUR", "MXN"),
    ) -> None:
        if not providers:
            raise ValueError("at least one exchange-rate provider is required")
        self._providers = tuple(providers)
        self._required = tuple(required_currencies)
        self.name = " > ".join(provider.name for provider in self._providers)

    def latest(self, base: str = "USD") -> RateTable:
        errors: list[str] = []
        for provider in self._providers:
            try:
                table = provider.latest(base)
            except ProviderUnavailableError as exc:
                logger.warning("Exchange provider %s failed: %s", provider.name, exc)
                errors.append(f"{provider.name}: {exc}")
                continue
            missing = [c for c in self._required if c != table.base and c not in table.rates]
            if missing:
                errors.append(f"{provider.name}: missing {','.join(missing)}")
                continue
            return table
        raise ProviderUnavailableError("; ".join(errors))


class CachedRateProvider:
    """Decorator: serve a cached table during ``ttl`` and the last good one (stale) on failure."""

    def __init__(
        self,
        inner: ExchangeRateProvider,
        ttl_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._inner = inner
        self._ttl = ttl_seconds
        self._clock = clock
        self._cache: dict[str, tuple[float, RateTable]] = {}
        self._lock = threading.Lock()
        self.name = inner.name

    def latest(self, base: str = "USD") -> RateTable:
        key = base.upper()
        cached = self._cache.get(key)
        if cached and self._clock() - cached[0] < self._ttl:
            return cached[1]
        try:
            table = self._inner.latest(key)
        except ProviderUnavailableError:
            if cached:
                return cached[1].mark_stale()
            raise
        with self._lock:
            self._cache[key] = (self._clock(), table)
        return table


def _dig(payload: Any, path: str) -> Any:
    current = payload
    for part in [segment for segment in path.split(".") if segment]:
        if isinstance(current, Mapping):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current


def _first(item: Mapping[str, Any], candidates: Sequence[str]) -> str:
    for key in candidates:
        value = _dig(item, key)
        if value not in (None, "", [], {}):
            if isinstance(value, list | tuple):
                return ", ".join(str(element) for element in value)
            return str(value)
    return ""


class HttpAllyCatalogAdapter(_HttpJsonAdapter):
    """Generic adapter for the allied team's JSON endpoint (field names are configurable)."""

    COMMON_COLLECTION_KEYS = ("results", "items", "data", "records", "latest_vacancies")

    def __init__(
        self,
        *,
        ally_name: str,
        url: str,
        items_path: str = "",
        title_fields: Sequence[str] = ("name", "title"),
        subtitle_fields: Sequence[str] = ("category",),
        description_fields: Sequence[str] = ("description",),
        url_fields: Sequence[str] = ("url",),
        api_key: str = "",
        max_items: int = 50,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._ally_name = ally_name
        self._url = url
        self._items_path = items_path
        self._fields = (title_fields, subtitle_fields, description_fields, url_fields)
        self._headers = {"Accept": "application/json"}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"
        self._max_items = max_items

    def fetch(self) -> AllyCatalog:
        payload = self._get_json(self._url, headers=self._headers)
        records = self._records(payload)
        title_f, subtitle_f, description_f, url_f = self._fields
        items: list[AllyItem] = []
        for record in records[: self._max_items]:
            if not isinstance(record, Mapping):
                items.append(AllyItem(title=str(record)))
                continue
            title = _first(record, title_f) or _first(record, ("id",))
            items.append(
                AllyItem(
                    title=title[:200],
                    subtitle=_first(record, subtitle_f)[:200],
                    description=_first(record, description_f)[:600],
                    url=_safe_url(_first(record, url_f)),
                )
            )
        return AllyCatalog(
            ally_name=self._ally_name,
            source_url=self._url,
            fetched_at=datetime.now(UTC),
            items=tuple(items),
        )

    def _records(self, payload: Any) -> list[Any]:
        if self._items_path:
            records = _dig(payload, self._items_path)
        elif isinstance(payload, list):
            records = payload
        elif isinstance(payload, Mapping):
            records = next(
                (payload[key] for key in self.COMMON_COLLECTION_KEYS if isinstance(payload.get(key), list)),
                [payload],
            )
        else:
            records = None
        if not isinstance(records, list):
            raise ProviderUnavailableError("ally payload does not contain a list of records")
        return records


def _safe_url(value: str) -> str:
    return value if value.startswith(("http://", "https://")) else ""


class UnconfiguredAllyCatalog:
    def fetch(self) -> AllyCatalog:
        raise IntegrationNotConfiguredError("ALLY_SERVICE_URL is not configured")


class CachedAllyCatalog:
    """Decorator that keeps the last successful ally catalog for degraded responses."""

    def __init__(
        self,
        inner: AllyCatalogProvider,
        ttl_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._inner = inner
        self._ttl = ttl_seconds
        self._clock = clock
        self._cached: tuple[float, AllyCatalog] | None = None

    def fetch(self) -> AllyCatalog:
        if self._cached and self._clock() - self._cached[0] < self._ttl:
            return self._cached[1]
        try:
            catalog = self._inner.fetch()
        except ProviderUnavailableError:
            if self._cached:
                previous = self._cached[1]
                return AllyCatalog(
                    ally_name=previous.ally_name,
                    source_url=previous.source_url,
                    fetched_at=previous.fetched_at,
                    items=previous.items,
                    stale=True,
                )
            raise
        self._cached = (self._clock(), catalog)
        return catalog
