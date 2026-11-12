import unittest
from decimal import Decimal

import requests

from integration_service.adapters import (
    CachedAllyCatalog,
    CachedRateProvider,
    FallbackRateProvider,
    FrankfurterAdapter,
    HttpAllyCatalogAdapter,
    OpenErApiAdapter,
    StaticRatesAdapter,
)
from integration_service.domain import ExchangeRateProvider, ProviderUnavailableError
from integration_service.resilience import CircuitBreaker
from tests.fakes import OPEN_ER_PAYLOAD, FakeResponse, FakeSession


def _kwargs(session, threshold=3, clock=None):
    breaker = CircuitBreaker("test", failure_threshold=threshold, reset_seconds=10)
    if clock:
        breaker._clock = clock
    return {"session": session, "timeout": 1, "breaker": breaker}


class ExchangeAdapterTests(unittest.TestCase):
    def test_open_er_api_adapter_translates_third_party_schema(self):
        session = FakeSession(FakeResponse(OPEN_ER_PAYLOAD))
        adapter = OpenErApiAdapter("https://example.test/v6/latest", **_kwargs(session))

        table = adapter.latest("usd")

        self.assertIsInstance(adapter, ExchangeRateProvider)
        self.assertEqual(session.calls[0][0], "https://example.test/v6/latest/USD")
        self.assertEqual(table.base, "USD")
        self.assertEqual(table.rates["COP"], Decimal("4000"))
        self.assertNotIn("BAD", table.rates)
        self.assertEqual(table.convert(Decimal("8000000"), "COP", "USD"), Decimal("2000.00"))
        self.assertEqual(table.convert(Decimal("100"), "EUR", "MXN"), Decimal("2055.56"))

    def test_open_er_api_error_payload_is_unavailable(self):
        session = FakeSession(FakeResponse({"result": "error"}))
        with self.assertRaises(ProviderUnavailableError):
            OpenErApiAdapter("https://x", **_kwargs(session)).latest()

    def test_frankfurter_adapter_uses_query_params(self):
        session = FakeSession(FakeResponse({"base": "USD", "rates": {"EUR": 0.9}}))
        table = FrankfurterAdapter("https://f.test/latest", **_kwargs(session)).latest()

        self.assertEqual(session.calls[0][1]["params"], {"base": "USD"})
        self.assertEqual(table.rates, {"EUR": Decimal("0.9")})

    def test_fallback_skips_failing_and_incomplete_providers(self):
        failing = OpenErApiAdapter("https://x", **_kwargs(FakeSession(requests.ConnectionError())))
        incomplete = FrankfurterAdapter(
            "https://f", **_kwargs(FakeSession(FakeResponse({"base": "USD", "rates": {"EUR": 0.9}})))
        )
        provider = FallbackRateProvider([failing, incomplete, StaticRatesAdapter()])

        table = provider.latest()

        self.assertEqual(table.provider, "static-reference")
        self.assertTrue(table.stale)

    def test_fallback_raises_when_everything_fails(self):
        failing = OpenErApiAdapter("https://x", **_kwargs(FakeSession(requests.Timeout())))
        with self.assertRaises(ProviderUnavailableError):
            FallbackRateProvider([failing]).latest()

    def test_cache_decorator_serves_cached_and_stale_tables(self):
        now = [0.0]
        session = FakeSession(FakeResponse(OPEN_ER_PAYLOAD), requests.ConnectionError())
        cached = CachedRateProvider(
            OpenErApiAdapter("https://x", **_kwargs(session, threshold=5)),
            ttl_seconds=60,
            clock=lambda: now[0],
        )

        first = cached.latest()
        cached.latest()
        now[0] = 120
        stale = cached.latest()

        self.assertEqual(len(session.calls), 2)
        self.assertFalse(first.stale)
        self.assertTrue(stale.stale)


class CircuitBreakerTests(unittest.TestCase):
    def test_opens_after_threshold_and_half_opens_after_timeout(self):
        now = [0.0]
        breaker = CircuitBreaker("x", failure_threshold=2, reset_seconds=10, clock=lambda: now[0])
        calls = []

        def boom():
            calls.append(1)
            raise RuntimeError("down")

        for _ in range(2):
            with self.assertRaises(RuntimeError):
                breaker.call(boom)
        self.assertEqual(breaker.state, "open")
        with self.assertRaises(Exception):
            breaker.call(boom)
        self.assertEqual(len(calls), 2)

        now[0] = 11
        self.assertEqual(breaker.state, "half_open")
        self.assertEqual(breaker.call(lambda: "ok"), "ok")
        self.assertEqual(breaker.state, "closed")


class AllyAdapterTests(unittest.TestCase):
    def _adapter(self, payload, **kwargs):
        return HttpAllyCatalogAdapter(
            ally_name="Equipo X",
            url="https://ally.test/api/products/",
            title_fields=("name", "title"),
            subtitle_fields=("category.name",),
            description_fields=("description",),
            url_fields=("url",),
            api_key="secret",
            **kwargs,
            **_kwargs(FakeSession(FakeResponse(payload))),
        )

    def test_maps_common_collections_and_nested_fields(self):
        payload = {
            "count": 2,
            "results": [
                {"name": "Curso Django", "category": {"name": "Cursos"}, "description": "Intro", "url": "https://a"},
                {"title": "Mentoria", "url": "javascript:alert(1)"},
            ],
        }
        adapter = self._adapter(payload)

        catalog = adapter.fetch()

        self.assertEqual(catalog.ally_name, "Equipo X")
        self.assertEqual([item.title for item in catalog.items], ["Curso Django", "Mentoria"])
        self.assertEqual(catalog.items[0].subtitle, "Cursos")
        self.assertEqual(catalog.items[1].url, "")
        headers = adapter._session.calls[0][1]["headers"]
        self.assertEqual(headers["Authorization"], "Bearer secret")

    def test_explicit_items_path_and_invalid_payload(self):
        catalog = self._adapter({"data": {"rows": [{"nombre": "x"}]}}, items_path="data.rows").fetch()
        self.assertEqual(len(catalog.items), 1)
        with self.assertRaises(ProviderUnavailableError):
            self._adapter({"data": {}}, items_path="data.rows").fetch()

    def test_cached_ally_catalog_degrades_to_stale(self):
        now = [0.0]
        session = FakeSession(FakeResponse([{"name": "A"}]), requests.ConnectionError())
        adapter = HttpAllyCatalogAdapter(ally_name="X", url="https://ally", **_kwargs(session, threshold=5))
        cached = CachedAllyCatalog(adapter, ttl_seconds=10, clock=lambda: now[0])

        cached.fetch()
        now[0] = 50
        degraded = cached.fetch()

        self.assertTrue(degraded.stale)
        self.assertEqual(degraded.items[0].title, "A")
