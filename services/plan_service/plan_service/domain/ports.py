"""Ports (Dependency Inversion) required by the application services."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from plan_service.domain.schemas import OrganizationProposal


@runtime_checkable
class OrganizationGenerator(Protocol):
    """Implemented by every AI provider adapter."""

    @property
    def name(self) -> str: ...

    def generate(self, company_description: str) -> OrganizationProposal: ...


@runtime_checkable
class EventPublisher(Protocol):
    """Publishes integration events to the message broker."""

    def publish(self, event_name: str, payload: dict[str, Any]) -> None: ...
