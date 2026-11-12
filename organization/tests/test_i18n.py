from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from organization.domain.exceptions import DomainValidationError
from organization.domain.validators import validate_company_description


@override_settings(AI_PROVIDER="MOCK")
class InternationalizationTests(TestCase):
    def test_spanish_is_the_default_language(self):
        response = self.client.get(reverse("organization:generate"))

        self.assertContains(response, '<html lang="es">')
        self.assertContains(response, "Generar estructura")

    def test_english_is_selected_from_accept_language(self):
        response = self.client.get(reverse("organization:generate"), HTTP_ACCEPT_LANGUAGE="en")

        self.assertContains(response, '<html lang="en">')
        self.assertContains(response, "Generate structure")
        self.assertContains(response, "Skip to content")
        self.assertContains(response, "Provider: MOCK")
        self.assertNotContains(response, "Generar estructura")

    def test_language_switcher_persists_choice(self):
        response = self.client.post(reverse("set_language"), {"language": "en", "next": "/planes/"})

        self.assertRedirects(response, "/planes/", fetch_redirect_response=False)
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "en")
        page = self.client.get(reverse("organization:history"))
        self.assertContains(page, "Generated plans")
        self.assertContains(page, "There are no plans yet")

    def test_form_errors_are_translated(self):
        response = self.client.post(
            reverse("organization:generate"),
            {"company_description": "too short"},
            HTTP_ACCEPT_LANGUAGE="en",
        )

        self.assertContains(response, "Describe the company with at least 80 characters.")

    def test_domain_messages_follow_active_language(self):
        with translation.override("en"), self.assertRaisesRegex(DomainValidationError, "at least 80"):
            validate_company_description("short")
        with translation.override("es"), self.assertRaisesRegex(DomainValidationError, "al menos 80"):
            validate_company_description("corta")

    def test_custom_404_page_is_translated(self):
        with self.settings(DEBUG=False):
            response = self.client.get("/planes/999999/", HTTP_ACCEPT_LANGUAGE="en")

        self.assertContains(response, "Page not found", status_code=404)
