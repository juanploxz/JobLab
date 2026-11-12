import unittest
from datetime import UTC, datetime
from decimal import Decimal

from integration_service import create_app
from integration_service.adapters import StaticRatesAdapter, UnconfiguredAllyCatalog
from integration_service.domain import AllyCatalog, AllyItem, ProviderUnavailableError, RateTable


class StubRates:
    name = "stub"

    def latest(self, base="USD"):
        return RateTable(
            base="USD",
            rates={"COP": Decimal("4000"), "EUR": Decimal("0.9"), "MXN": Decimal("18"), "USD": Decimal(1)},
            provider="stub",
            fetched_at=datetime(2026, 11, 12, tzinfo=UTC),
        )


class DownRates:
    name = "down"

    def latest(self, base="USD"):
        raise ProviderUnavailableError("down")


class StubAlly:
    def fetch(self):
        return AllyCatalog(
            ally_name="Equipo aliado",
            source_url="https://ally.test",
            fetched_at=datetime(2026, 11, 12, tzinfo=UTC),
            items=(AllyItem(title="Producto", subtitle="Cat", description="Desc", url="https://x"),),
        )


def make_client(rates=None, ally=None):
    app = create_app(
        {
            "TESTING": True,
            "EXCHANGE_PROVIDER": rates or StubRates(),
            "ALLY_CATALOG": ally or StubAlly(),
        }
    )
    return app.test_client()


class IntegrationApiTests(unittest.TestCase):
    def test_rates_rebased_and_filtered(self):
        response = make_client().get("/api/v2/rates/?base=COP&symbols=USD,EUR")

        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["base"], "COP")
        self.assertEqual(set(body["rates"]), {"USD", "EUR"})
        self.assertEqual(body["rates"]["USD"], "0.00025")
        self.assertEqual(response.headers["X-API-Version"], "v2")

    def test_unknown_symbol_is_400(self):
        response = make_client().get("/api/v2/rates/?symbols=XYZ")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"]["code"], "unsupported_currency")

    def test_batch_salary_conversion(self):
        response = make_client().post(
            "/api/v2/salaries/convert/",
            json={
                "target": "usd",
                "items": [{"id": 7, "salary_min": "4000000", "salary_max": "8000000", "currency": "COP"}],
            },
        )

        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["target"], "USD")
        self.assertEqual(body["items"][0], {
            "id": 7,
            "salary_min": "1000.00",
            "salary_max": "2000.00",
            "original_currency": "COP",
            "rate": "0.00025",
        })

    def test_invalid_conversion_requests(self):
        client = make_client()
        cases = [
            {"target": "ARS", "items": []},
            {"target": "USD", "items": [{"salary_min": "9", "salary_max": "1", "currency": "COP"}]},
            {"target": "USD", "items": "nope"},
            {"target": 5},
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                response = client.post("/api/v2/salaries/convert/", json=payload)
                self.assertEqual(response.status_code, 400)
        malformed = client.post("/api/v2/salaries/convert/", data="{", content_type="application/json")
        self.assertEqual(malformed.get_json()["error"]["code"], "parse_error")

    def test_provider_down_returns_503(self):
        response = make_client(rates=DownRates()).get("/api/v2/rates/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"]["code"], "provider_unavailable")

    def test_static_adapter_rebases(self):
        table = StaticRatesAdapter().latest("COP")
        self.assertEqual(table.base, "COP")
        self.assertTrue(table.stale)

    def test_ally_catalog_and_unconfigured_ally(self):
        ok = make_client().get("/api/v2/ally/")
        missing = make_client(ally=UnconfiguredAllyCatalog()).get(
            "/api/v2/ally/", headers={"Accept-Language": "en"}
        )

        self.assertEqual(ok.get_json()["items"][0]["title"], "Producto")
        self.assertEqual(missing.status_code, 503)
        self.assertEqual(missing.get_json()["error"]["code"], "ally_not_configured")
        self.assertIn("allied team", missing.get_json()["error"]["detail"])

    def test_health(self):
        response = make_client().get("/health")

        self.assertEqual(response.get_json()["status"], "ok")
