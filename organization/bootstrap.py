from organization.infra.ai.factory import AIProviderFactory
from organization.services import GenerateOrganizationService


def build_generation_service() -> GenerateOrganizationService:
    """Composition root: infrastructure is selected outside the service layer."""
    provider = AIProviderFactory.create()
    return GenerateOrganizationService(ai_provider=provider)
