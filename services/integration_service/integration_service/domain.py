"""Domain model and ports of the external-integrations bounded context.

Application services depend only on the ``ExchangeRateProvider`` and
``AllyCatalogProvider`` ports (Dependency Inversion). Each third-party API is
translated to these neutral types by an Adapter in ``integration_service.adapters``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from typing import Protocol, runtime_checkable


class IntegrationError(RuntimeError):
    """Base class for failures of an external integration."""


class ProviderUnavailableError(IntegrationError):
    """The external provider failed, timed out or returned an unexpected schema."""


class IntegrationNotConfiguredError(IntegrationError):
    """The integration has no endpoint configured."""


class UnsupportedCurrencyError(ValueError):
    def __init__(self, currency: str) -> None:
        super().__init__(currency)
        self.currency = currency


@dataclass(frozen=True, slots=True)
class RateTable:
    """Units of each currency per one unit of ``base``."""

    base: str
    rates: dict[str, Decimal]
    provider: str
    fetched_at: datetime
    stale: bool = False

    def rate(self, source: str, target: str) -> Decimal:
        source, target = source.upper(), target.upper()
        for currency in (source, target):
            if currency != self.base and currency not in self.rates:
                raise UnsupportedCurrencyError(currency)
        source_rate = Decimal(1) if source == self.base else self.rates[source]
        target_rate = Decimal(1) if target == self.base else self.rates[target]
        return target_rate / source_rate

    def convert(self, amount: Decimal, source: str, target: str) -> Decimal:
        return (Decimal(amount) * self.rate(source, target)).quantize(Decimal("0.01"))

    def rebased(self, base: str) -> RateTable:
        base = base.upper()
        rates = {currency: self.rate(base, currency) for currency in {*self.rates, self.base}}
        return replace(self, base=base, rates=rates)

    def mark_stale(self) -> RateTable:
        return replace(self, stale=True)


@dataclass(frozen=True, slots=True)
class AllyItem:
    title: str
    subtitle: str = ""
    description: str = ""
    url: str = ""


@dataclass(frozen=True, slots=True)
class AllyCatalog:
    ally_name: str
    source_url: str
    fetched_at: datetime
    items: tuple[AllyItem, ...] = field(default_factory=tuple)
    stale: bool = False


@runtime_checkable
class ExchangeRateProvider(Protocol):
    name: str

    def latest(self, base: str = "USD") -> RateTable: ...


@runtime_checkable
class AllyCatalogProvider(Protocol):
    def fetch(self) -> AllyCatalog: ...
