from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from plan_service.domain.exceptions import ConfigurationError
from plan_service.domain.ports import OrganizationGenerator
from plan_service.infra.ai.google_provider import GoogleOrganizationProvider
from plan_service.infra.ai.mock_provider import MockOrganizationProvider


class AIProviderFactory:
    """Factory Method: select the concrete AI adapter from configuration."""

    @staticmethod
    def create(config: Mapping[str, Any], provider_name: str | None = None) -> OrganizationGenerator:
        selected = (provider_name or config.get("AI_PROVIDER") or "MOCK").strip().upper()
        if selected == "MOCK":
            return MockOrganizationProvider()
        if selected == "GOOGLE":
            return GoogleOrganizationProvider(
                api_key=config.get("GEMINI_API_KEY", ""),
                model=config.get("GEMINI_MODEL", "gemini-2.5-flash-lite"),
                timeout_ms=int(config.get("GEMINI_TIMEOUT_MS", 60_000)),
            )
        raise ConfigurationError(f"AI_PROVIDER={selected!r} is not valid. Use MOCK or GOOGLE.")
