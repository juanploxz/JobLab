from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from organization.domain.exceptions import ServiceUnavailableError
from organization.gateways.http import UnavailableGateway, plan_from_json
from organization.tests.test_gateways import PLAN_JSON

TASK_ID = "0f8fad5b-d9cb-469f-a165-70867728950e"


class FakePlanGateway:
    name = "plan-service"

    def __init__(self):
        self.generated = []

    def generate_plan(self, description):
        self.generated.append(description)
        return 5

    def get_plan(self, plan_id):
        return plan_from_json(PLAN_JSON)

    def list_plans(self, page, page_size):
        from organization.dtos import PlanPageDTO, PlanSummaryDTO

        plan = plan_from_json(PLAN_JSON)
        summary = PlanSummaryDTO(
            id=plan.id,
            company_name=plan.company_name,
            company_summary=plan.company_summary,
            review_status=plan.review_status,
            generation_status=plan.generation_status,
            provider_name=plan.provider_name,
            created_at=plan.created_at,
        )
        return PlanPageDTO(items=(summary,), count=1, page=page, page_size=page_size)


class FakeIntegrationGateway:
    def convert_salaries(self, target, vacancies):
        return {
            "target": "USD",
            "provider": "open.er-api.com",
            "stale": False,
            "items": [{"id": 9, "salary_min": "1000.00", "salary_max": "1500.00"}],
        }

    def ally_catalog(self):
        return {
            "ally": "Equipo Aliado",
            "count": 1,
            "stale": False,
            "items": [{"title": "Curso de Liderazgo", "subtitle": "Cursos", "description": "", "url": "https://ally.test"}],
        }


class FakeReportGateway:
    def __init__(self, status="PENDING"):
        self.status = status

    def request_report(self, plan_id, report_format):
        return {"task_id": TASK_ID, "status": "PENDING"}

    def report_status(self, task_id):
        return {"task_id": task_id, "plan_id": 5, "format": "csv", "status": self.status, "error": None}

    def download(self, task_id):
        return b"a,b\n", "text/csv; charset=utf-8", 'attachment; filename="joblab-plan-5.csv"'

    def notifications(self, limit=20):
        return [
            {
                "type": "plan.created",
                "created_at": "2026-11-12T10:00:00+00:00",
                "data": {"plan_id": 5, "company_name": "Empresa Demo", "vacancy_count": 1},
            }
        ]


def gateways(plan=None, integration=None, report=None):
    return (
        patch("organization.views.factory.build_plan_gateway", return_value=plan or FakePlanGateway()),
        patch(
            "organization.views.factory.build_integration_gateway",
            return_value=integration or FakeIntegrationGateway(),
        ),
        patch("organization.views.factory.build_report_gateway", return_value=report or FakeReportGateway()),
    )


class MicroserviceBackedViewsTests(TestCase):
    def setUp(self):
        self.patches = gateways()
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_generate_goes_through_plan_gateway(self):
        response = self.client.post(reverse("organization:generate"), {"company_description": "x" * 100})

        self.assertRedirects(response, reverse("organization:detail", args=(5,)), fetch_redirect_response=False)

    def test_detail_renders_tree_and_usd_from_integration_service(self):
        response = self.client.get(reverse("organization:detail", args=(5,)))

        self.assertContains(response, "Desarrollador")
        self.assertContains(response, "Equivalente USD")
        # Spanish number format uses a non-breaking space as thousands separator.
        self.assertContains(response, "USD $1\u00a0000 - $1\u00a0500")
        self.assertContains(response, "open.er-api.com")
        self.assertContains(response, reverse("organization:request-report", args=(5,)))

    def test_history_uses_gateway_page(self):
        response = self.client.get(reverse("organization:history"))

        self.assertContains(response, "Empresa Demo")
        self.assertContains(response, "1 plan registrado.")

    def test_report_request_redirects_to_status_and_download(self):
        response = self.client.post(reverse("organization:request-report", args=(5,)), {"format": "csv"})
        self.assertRedirects(
            response, reverse("organization:report-status", args=(TASK_ID,)), fetch_redirect_response=False
        )

        status = self.client.get(reverse("organization:report-status", args=(TASK_ID,)))
        self.assertContains(status, 'http-equiv="refresh"')
        self.assertContains(status, "En proceso")

        download = self.client.get(reverse("organization:report-download", args=(TASK_ID,)))
        self.assertEqual(download["Content-Disposition"], 'attachment; filename="joblab-plan-5.csv"')

    def test_invalid_report_format_and_task_id(self):
        response = self.client.post(reverse("organization:request-report", args=(5,)), {"format": "pdf"}, follow=True)
        self.assertContains(response, "Selecciona un formato de reporte válido.")
        self.assertEqual(self.client.get("/reportes/not-valid/").status_code, 404)

    def test_ally_activity_and_status_pages(self):
        self.assertContains(self.client.get(reverse("organization:ally")), "Curso de Liderazgo")
        self.assertContains(
            self.client.get(reverse("organization:activity")), "Se generó el plan #5 para Empresa Demo"
        )
        status = self.client.get(reverse("organization:status"))
        self.assertContains(status, "django-db")
        self.assertContains(status, "plan-service")


class DegradedModeTests(TestCase):
    def test_plan_service_down_renders_503_page(self):
        class DownPlanGateway(FakePlanGateway):
            def get_plan(self, plan_id):
                raise ServiceUnavailableError("plan-service", "timeout")

        with patch("organization.views.factory.build_plan_gateway", return_value=DownPlanGateway()):
            response = self.client.get(reverse("organization:detail", args=(5,)))

        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "plan-service", status_code=503)

    def test_detail_still_works_without_integration_service(self):
        patches = gateways(integration=UnavailableGateway("integration-service"))
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

        response = self.client.get(reverse("organization:detail", args=(5,)))

        self.assertContains(response, "La conversión a USD no está disponible")
        self.assertNotContains(response, "Equivalente USD")

    def test_unconfigured_services_show_friendly_messages(self):
        patches = gateways(
            integration=UnavailableGateway("integration-service"),
            report=UnavailableGateway("report-service"),
        )
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

        self.assertContains(self.client.get(reverse("organization:ally")), "El servicio aliado no está disponible")
        self.assertContains(
            self.client.get(reverse("organization:activity")), "El servicio de notificaciones no está disponible"
        )
        response = self.client.post(reverse("organization:request-report", args=(5,)), {"format": "csv"}, follow=True)
        self.assertContains(response, "El servicio de reportes no está disponible")
