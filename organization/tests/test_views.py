from django.test import TestCase, override_settings
from django.urls import reverse

from organization.forms import COMPANY_DESCRIPTION_HELP
from organization.models import OrganizationalPlan
from organization.tests.test_services import DESCRIPTION


@override_settings(AI_PROVIDER="MOCK")
class GenerateOrganizationViewTests(TestCase):
    def test_get_renders_accessible_help_and_mock_provider(self):
        response = self.client.get(reverse("organization:generate"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, COMPANY_DESCRIPTION_HELP)
        self.assertContains(response, 'aria-describedby="company-description-help')
        self.assertContains(response, "Proveedor: MOCK")

    def test_post_delegates_generation_and_redirects_to_plan(self):
        response = self.client.post(
            reverse("organization:generate"),
            {"company_description": DESCRIPTION},
        )

        plan = OrganizationalPlan.objects.get()
        self.assertRedirects(response, reverse("organization:detail", args=(plan.pk,)))

    def test_detail_displays_structure_vacancies_and_disclaimer(self):
        self.client.post(
            reverse("organization:generate"),
            {"company_description": DESCRIPTION},
        )
        plan = OrganizationalPlan.objects.get()

        response = self.client.get(reverse("organization:detail", args=(plan.pk,)))

        self.assertContains(response, "Estructura propuesta")
        self.assertContains(response, "Desarrollador Full Stack")
        self.assertContains(response, "Los salarios son aproximaciones")

    def test_invalid_description_stays_on_form(self):
        response = self.client.post(
            reverse("organization:generate"),
            {"company_description": "Una descripcion demasiado corta"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "80 caracteres")
        self.assertFalse(OrganizationalPlan.objects.exists())
