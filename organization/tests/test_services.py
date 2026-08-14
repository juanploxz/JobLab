from django.test import TestCase

from organization.domain.exceptions import GenerationError
from organization.infra.ai.mock_provider import MockOrganizationProvider
from organization.models import OrganizationalPlan, OrganizationGenerationRequest, Vacancy
from organization.services import GenerateOrganizationService


DESCRIPTION = (
    "Somos una empresa de software en Medellin que construira una plataforma para "
    "automatizar la planeacion de equipos en pequenas empresas. Tenemos presupuesto "
    "para un equipo inicial y queremos crecer despues de validar el producto."
)


class FailingProvider:
    name = "FAILING"

    def generate(self, company_description):
        raise TimeoutError("El proveedor no respondio")


class GenerateOrganizationServiceTests(TestCase):
    def test_persists_complete_plan_in_one_use_case(self):
        plan = GenerateOrganizationService(MockOrganizationProvider()).execute(DESCRIPTION)

        request = plan.request
        self.assertEqual(request.status, OrganizationGenerationRequest.Status.COMPLETED)
        self.assertEqual(request.provider_name, "MOCK")
        self.assertGreaterEqual(plan.units.count(), 4)
        self.assertGreaterEqual(plan.vacancies.count(), 5)
        self.assertEqual(
            sum(vacancy.available_positions for vacancy in Vacancy.objects.filter(plan=plan)),
            7,
        )

    def test_marks_request_failed_without_partial_plan(self):
        service = GenerateOrganizationService(FailingProvider())

        with self.assertRaises(GenerationError):
            service.execute(DESCRIPTION)

        request = OrganizationGenerationRequest.objects.get()
        self.assertEqual(request.status, OrganizationGenerationRequest.Status.FAILED)
        self.assertIn("proveedor", request.error_message)
        self.assertFalse(OrganizationalPlan.objects.exists())

    def test_rejects_short_description_before_creating_request(self):
        service = GenerateOrganizationService(MockOrganizationProvider())

        with self.assertRaises(ValueError):
            service.execute("Muy corta")

        self.assertFalse(OrganizationGenerationRequest.objects.exists())
