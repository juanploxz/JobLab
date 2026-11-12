"""Application services that depend only on domain ports."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from integration_service.domain import (
    AllyCatalog,
    AllyCatalogProvider,
    ExchangeRateProvider,
    RateTable,
    UnsupportedCurrencyError,
)

SUPPORTED_TARGETS = ("COP", "USD", "EUR", "MXN")


class InvalidConversionRequest(ValueError):
    def __init__(self, detail_key: str, **params: Any) -> None:
        super().__init__(detail_key)
        self.detail_key = detail_key
        self.params = params


@dataclass(frozen=True, slots=True)
class ConvertedSalary:
    id: Any
    salary_min: Decimal
    salary_max: Decimal
    original_currency: str
    rate: Decimal


class GetExchangeRatesService:
    def __init__(self, provider: ExchangeRateProvider) -> None:
        self._provider = provider

    def execute(self, base: str, symbols: tuple[str, ...] = ()) -> RateTable:
        base = (base or "USD").upper()
        table = self._provider.latest("USD")
        rebased = table if base == table.base else table.rebased(base)
        if symbols:
            wanted = {symbol.upper() for symbol in symbols}
            missing = sorted(wanted - set(rebased.rates) - {rebased.base})
            if missing:
                raise UnsupportedCurrencyError(missing[0])
            rebased = RateTable(
                base=rebased.base,
                rates={code: rate for code, rate in rebased.rates.items() if code in wanted},
                provider=rebased.provider,
                fetched_at=rebased.fetched_at,
                stale=rebased.stale,
            )
        return rebased


class ConvertSalariesService:
    """Convert vacancy salary ranges to a target currency in one call."""

    def __init__(self, provider: ExchangeRateProvider, max_items: int = 200) -> None:
        self._provider = provider
        self._max_items = max_items

    def execute(self, target: str, items: list[dict[str, Any]]) -> tuple[RateTable, list[ConvertedSalary]]:
        target = (target or "").upper()
        if target not in SUPPORTED_TARGETS:
            raise InvalidConversionRequest("unsupported_target", options=", ".join(SUPPORTED_TARGETS))
        if not isinstance(items, list) or len(items) > self._max_items:
            raise InvalidConversionRequest("invalid_items", maximum=self._max_items)

        table = self._provider.latest("USD")
        converted: list[ConvertedSalary] = []
        for item in items:
            if not isinstance(item, dict):
                raise InvalidConversionRequest("invalid_items", maximum=self._max_items)
            try:
                minimum = Decimal(str(item["salary_min"]))
                maximum = Decimal(str(item["salary_max"]))
                currency = str(item["currency"]).upper()
            except (KeyError, InvalidOperation, ValueError) as exc:
                raise InvalidConversionRequest("invalid_items", maximum=self._max_items) from exc
            if not minimum.is_finite() or not maximum.is_finite() or minimum < 0 or minimum > maximum:
                raise InvalidConversionRequest("invalid_range")
            converted.append(
                ConvertedSalary(
                    id=item.get("id"),
                    salary_min=table.convert(minimum, currency, target),
                    salary_max=table.convert(maximum, currency, target),
                    original_currency=currency,
                    rate=table.rate(currency, target),
                )
            )
        return table, converted


class GetAllyCatalogService:
    def __init__(self, provider: AllyCatalogProvider) -> None:
        self._provider = provider

    def execute(self) -> AllyCatalog:
        return self._provider.fetch()
