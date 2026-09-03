from unittest.mock import patch

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from organization.api.serializers import CreateVacancyInputSerializer
from organization.api.views import PlanCollectionAPIView
from organization.domain.exceptions import GenerationError
from organization.models import OrganizationalPlan, OrganizationGenerationRequest, Vacancy
from organization.tests.test_services import DESCRIPTION


@override_settings(ROOT_URLCONF="organization.api.urls", AI_PROVIDER="MOCK")
class OrganizationAPITests(APITestCase):
    plans_url = "/plans/"

    def generate_plan(self) -> OrganizationalPlan:
        response = self.client.post(
            self.plans_url,
            {"company_description": DESCRIPTION},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return OrganizationalPlan.objects.get(pk=response.data["id"])

    def valid_vacancy_payload(self, department_id: int) -> dict:
        return {
            "department_id": department_id,
            "name": "Arquitecto de Integraciones",
            "available_positions": 1,
            "salary_min": "6500000.00",
            "salary_max": "8500000.00",
            "currency": "COP",
            "salary_period": "MONTHLY",
            "description": (
                "Disena integraciones confiables, documenta contratos y mantiene "
                "pruebas automatizadas de los servicios empresariales."
            ),
            "required_knowledge": ["Python", "Django REST Framework"],
            "reports_to": "Lider Tecnico",
        }

    def test_post_plan_returns_201_location_and_complete_output(self):
        response = self.client.post(
            self.plans_url,
            {"company_description": DESCRIPTION},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response["Location"].endswith(f"/plans/{response.data['id']}/"))
        self.assertEqual(response.data["generation_status"], "COMPLETED")
        self.assertGreaterEqual(response.data["metrics"]["department_count"], 1)
        self.assertGreaterEqual(response.data["metrics"]["vacancy_count"], 1)
        self.assertTrue(response.data["units"])
        self.assertTrue(response.data["vacancies"])

    def test_get_plan_collection_returns_serialized_summaries(self):
        first_plan = self.generate_plan()
        self.generate_plan()

        response = self.client.get(f"{self.plans_url}?page_size=1")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertNotEqual(response.data["results"][0]["id"], first_plan.pk)
        self.assertEqual(response.data["results"][0]["generation_status"], "COMPLETED")

    def test_invalid_collection_page_returns_uniform_404(self):
        self.generate_plan()

        response = self.client.get(f"{self.plans_url}?page=999999")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "page_not_found")

    def test_get_plan_detail_returns_200_and_service_metrics(self):
        plan = self.generate_plan()

        response = self.client.get(f"/plans/{plan.pk}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], plan.pk)
        self.assertEqual(
            response.data["metrics"]["total_positions"],
            sum(v.available_positions for v in plan.vacancies.all()),
        )

    def test_get_missing_plan_returns_uniform_404(self):
        response = self.client.get("/plans/999999/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "plan_not_found")
        self.assertIn("detail", response.data["error"])

    def test_missing_transport_field_returns_uniform_400(self):
        response = self.client.post(self.plans_url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "invalid_request")
        self.assertIn("company_description", response.data["error"]["fields"])
        self.assertFalse(OrganizationGenerationRequest.objects.exists())

    def test_malformed_json_returns_uniform_400(self):
        response = self.client.generic(
            "POST",
            self.plans_url,
            '{"company_description":',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "parse_error")
        self.assertIn("detail", response.data["error"])

    def test_method_not_allowed_uses_uniform_error_contract(self):
        response = self.client.delete(self.plans_url)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(response.data["error"]["code"], "method_not_allowed")

    def test_domain_validation_returns_uniform_400(self):
        response = self.client.post(
            self.plans_url,
            {"company_description": "Descripcion demasiado corta"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "domain_validation_error")
        self.assertFalse(OrganizationGenerationRequest.objects.exists())

    def test_generation_failure_returns_uniform_503(self):
        class UnavailableGenerationService:
            def execute(self, company_description):
                raise GenerationError("Detalle interno que no debe exponerse")

        factory = staticmethod(lambda: UnavailableGenerationService())
        with patch.object(PlanCollectionAPIView, "generation_service_factory", factory):
            response = self.client.post(
                self.plans_url,
                {"company_description": DESCRIPTION},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(
            response.data["error"]["code"],
            "generation_service_unavailable",
        )
        self.assertNotIn("Detalle interno", response.data["error"]["detail"])

    def test_post_vacancy_returns_201_and_location(self):
        plan = self.generate_plan()
        department = plan.units.first()
        payload = self.valid_vacancy_payload(department.pk)

        response = self.client.post(
            f"/plans/{plan.pk}/vacancies/",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            response["Location"].endswith(
                f"/plans/{plan.pk}/vacancies/{response.data['id']}/"
            )
        )
        self.assertEqual(response.data["department_id"], department.pk)
        self.assertTrue(Vacancy.objects.filter(pk=response.data["id"]).exists())

        detail_response = self.client.get(
            f"/plans/{plan.pk}/vacancies/{response.data['id']}/"
        )
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["id"], response.data["id"])

    def test_missing_vacancy_returns_uniform_404(self):
        plan = self.generate_plan()

        response = self.client.get(f"/plans/{plan.pk}/vacancies/999999/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "vacancy_not_found")

    def test_duplicate_vacancy_returns_uniform_409(self):
        plan = self.generate_plan()
        department = plan.units.first()
        payload = self.valid_vacancy_payload(department.pk)
        url = f"/plans/{plan.pk}/vacancies/"
        first_response = self.client.post(url, payload, format="json")

        response = self.client.post(url, payload, format="json")

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "vacancy_already_exists")
        self.assertEqual(
            Vacancy.objects.filter(
                plan=plan,
                department=department,
                name=payload["name"],
            ).count(),
            1,
        )

    def test_duplicate_vacancy_is_case_insensitive(self):
        plan = self.generate_plan()
        department = plan.units.first()
        payload = self.valid_vacancy_payload(department.pk)
        url = f"/plans/{plan.pk}/vacancies/"
        first_response = self.client.post(url, payload, format="json")
        payload["name"] = payload["name"].swapcase()

        response = self.client.post(url, payload, format="json")

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "vacancy_already_exists")

    def test_vacancy_for_missing_plan_returns_uniform_404(self):
        payload = self.valid_vacancy_payload(1)

        response = self.client.post("/plans/999999/vacancies/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "plan_not_found")

    def test_vacancy_for_department_outside_plan_returns_uniform_404(self):
        first_plan = self.generate_plan()
        second_plan = self.generate_plan()
        foreign_department = second_plan.units.first()
        payload = self.valid_vacancy_payload(foreign_department.pk)

        response = self.client.post(
            f"/plans/{first_plan.pk}/vacancies/",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "department_not_found")

    def test_business_rule_is_checked_by_service_not_input_serializer(self):
        plan = self.generate_plan()
        department = plan.units.first()
        payload = self.valid_vacancy_payload(department.pk)
        payload["salary_min"] = "9000000.00"
        payload["salary_max"] = "5000000.00"
        self.assertTrue(CreateVacancyInputSerializer(data=payload).is_valid())

        response = self.client.post(
            f"/plans/{plan.pk}/vacancies/",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "domain_validation_error")
