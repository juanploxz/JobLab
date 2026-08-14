from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from organization.domain.ports import OrganizationGenerator
from organization.infra.ai.google_provider import GoogleOrganizationProvider
from organization.infra.ai.mock_provider import MockOrganizationProvider


class AIProviderFactory:
    """Select the concrete provider from environment-backed Django settings."""

    @staticmethod
    def create(provider_name: str | None = None) -> OrganizationGenerator:
        selected = (provider_name or settings.AI_PROVIDER).strip().upper()
        if selected == "MOCK":
            return MockOrganizationProvider()
        if selected == "GOOGLE":
            return GoogleOrganizationProvider()
        raise ImproperlyConfigured(
            f"AI_PROVIDER={selected!r} no es valido. Usa MOCK o GOOGLE."
        )
