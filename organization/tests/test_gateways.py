from unittest import TestCase

import requests

from organization.domain.exceptions import (
    DomainValidationError,
    GenerationError,
    ResourceNotFoundError,
    ServiceUnavailableError,
)
from organization.gateways.http import HttpIntegrationGateway, HttpPlanGateway, HttpReportGateway
from organization.gateways.resilience import CircuitBreaker, ServiceClient

PLAN_JSON = {
    "id": 5,
    "request_id": 5,
    "company_name": "Empresa Demo",
    "company_summary": "Resumen de la empresa con suficiente longitud para el contrato.",
    "assumptions": ["Supuesto"],
    "review_status": "DRAFT",
    "generation_status": "COMPLETED",
    "provider_name": "MOCK",
    "created_at": "2026-11-12T10:00:00+00:00",
    "metrics": {"department_count": 2, "vacancy_count": 1, "total_positions": 3},
    "units": [
        {"id": 1, "code": "ROOT", "name": "Direccion", "description": "d", "parent_id": None},
        {"id": 2, "code": "TECH", "name": "Tecnologia", "description": "t", "parent_id": 1},
    ],
    "vacancies": [
        {
            "id": 9,
            "plan_id": 5,
            "department_id": 2,
            "department_name": "Tecnologia",
            "name": "Desarrollador",
            "available_positions": 3,
            "salary_min": "4000000.00",
            "salary_max": "6000000.00",
            "currency": "COP",
            "salary_period": "MONTHLY",
            "description": "Construye el producto.",
            "required_knowledge": ["Python"],
            "reports_to": "",
            "status": "DRAFT",
            "created_at": "2026-11-12T10:00:00+00:00",
        }
    ],
}


class FakeResponse:
    def __init__(self, status_code, payload=None, headers=None, content=b""):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.content = content

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(response, Exception):
            raise response
        return response


def client(*responses, threshold=3):
    session = FakeSession(*responses)
    return (
        ServiceClient(
            "plan-service",
            "http://plan.test/",
            breaker=CircuitBreaker(failure_threshold=threshold, reset_seconds=60),
            session=session,
            context=lambda: {"Accept-Language": "en", "X-Request-ID": "req-1"},
        ),
        session,
    )


class HttpPlanGatewayTests(TestCase):
    def test_get_plan_maps_contract_to_dtos_and_propagates_context(self):
        service_client, session = client(FakeResponse(200, PLAN_JSON))

        plan = HttpPlanGateway(service_client).get_plan(5)

        method, url, kwargs = session.calls[0]
        self.assertEqual((method, url), ("GET", "http://plan.test/api/v2/plans/5/"))
        self.assertEqual(kwargs["headers"]["Accept-Language"], "en")
        self.assertEqual(kwargs["headers"]["X-Request-ID"], "req-1")
        self.assertEqual(plan.metrics.total_positions, 3)
        self.assertEqual(plan.vacancies[0].salary_min, 4000000)
        self.assertEqual(plan.units[1].parent_id, 1)

    def test_generate_plan_translates_errors(self):
        created, _ = client(FakeResponse(201, {"id": 8}))
        invalid, _ = client(FakeResponse(400, {"error": {"code": "domain_validation_error", "detail": "Muy corta"}}))
        down, _ = client(requests.ConnectionError("refused"))

        self.assertEqual(HttpPlanGateway(created).generate_plan("x" * 90), 8)
        with self.assertRaisesRegex(DomainValidationError, "Muy corta"):
            HttpPlanGateway(invalid).generate_plan("x")
        with self.assertRaises(GenerationError):
            HttpPlanGateway(down).generate_plan("x" * 90)

    def test_missing_plan_and_pagination(self):
        missing, _ = client(FakeResponse(404, {"error": {"code": "plan_not_found", "detail": "No existe"}}))
        listing, session = client(
            FakeResponse(200, {"count": 13, "results": [{**PLAN_JSON, "company_summary": "s"}]})
        )

        with self.assertRaises(ResourceNotFoundError):
            HttpPlanGateway(missing).get_plan(99)
        page = HttpPlanGateway(listing).list_plans(2, 12)
        self.assertEqual(session.calls[0][2]["params"], {"page": 2, "page_size": 12})
        self.assertEqual(page.num_pages, 2)
        self.assertTrue(page.has_previous)
        self.assertFalse(page.has_next)

    def test_circuit_opens_after_consecutive_failures(self):
        service_client, session = client(FakeResponse(503, {}), threshold=2)
        gateway = HttpPlanGateway(service_client)

        for _ in range(2):
            with self.assertRaises(ServiceUnavailableError):
                gateway.get_plan(1)
        with self.assertRaisesRegex(ServiceUnavailableError, "circuit open"):
            gateway.get_plan(1)
        self.assertEqual(len(session.calls), 2)


class OtherGatewaysTests(TestCase):
    def test_integration_gateway_ally_not_configured(self):
        service_client, _ = client(
            FakeResponse(503, {"error": {"code": "ally_not_configured"}}), threshold=1
        )
        gateway = HttpIntegrationGateway(service_client)

        for _ in range(2):
            with self.assertRaises(ServiceUnavailableError) as raised:
                gateway.ally_catalog()
            self.assertEqual(raised.exception.detail, "ally_not_configured")
        # The allied service's 503 must not open integration-service's circuit.
        self.assertEqual(service_client.breaker.state, "closed")

    def test_report_gateway_flow(self):
        service_client, session = client(
            FakeResponse(202, {"task_id": "a" * 32, "status": "PENDING"}),
            FakeResponse(200, {"task_id": "a" * 32, "status": "SUCCESS"}),
            FakeResponse(200, None, {"Content-Type": "text/csv", "Content-Disposition": "attachment"}, b"x,y"),
        )
        gateway = HttpReportGateway(service_client)

        self.assertEqual(gateway.request_report(5, "csv")["status"], "PENDING")
        self.assertEqual(gateway.report_status("a" * 32)["status"], "SUCCESS")
        content, content_type, _ = gateway.download("a" * 32)
        self.assertEqual((content, content_type), (b"x,y", "text/csv"))
        self.assertEqual(session.calls[0][2]["json"], {"plan_id": 5, "format": "csv"})
