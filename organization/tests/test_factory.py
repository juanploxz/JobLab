from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from organization.infra.ai.factory import AIProviderFactory
from organization.infra.ai.google_provider import GoogleOrganizationProvider
from organization.infra.ai.mock_provider import MockOrganizationProvider


class AIProviderFactoryTests(SimpleTestCase):
    @override_settings(AI_PROVIDER="MOCK")
    def test_returns_mock_provider_from_environment_setting(self):
        self.assertIsInstance(AIProviderFactory.create(), MockOrganizationProvider)

    @override_settings(AI_PROVIDER="GOOGLE", GEMINI_API_KEY="not-a-real-key")
    def test_returns_google_provider_from_environment_setting(self):
        self.assertIsInstance(AIProviderFactory.create(), GoogleOrganizationProvider)

    def test_explicit_provider_overrides_setting(self):
        self.assertIsInstance(AIProviderFactory.create("mock"), MockOrganizationProvider)

    def test_rejects_unknown_provider(self):
        with self.assertRaisesRegex(ImproperlyConfigured, "MOCK o GOOGLE"):
            AIProviderFactory.create("UNKNOWN")

    @override_settings(GEMINI_API_KEY="")
    def test_google_provider_requires_api_key(self):
        with self.assertRaisesRegex(ImproperlyConfigured, "GEMINI_API_KEY"):
            GoogleOrganizationProvider()
