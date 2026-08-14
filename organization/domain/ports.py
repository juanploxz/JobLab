from typing import Protocol, runtime_checkable

from organization.domain.schemas import OrganizationProposal


@runtime_checkable
class OrganizationGenerator(Protocol):
    """Port implemented by every organization-generation provider."""

    @property
    def name(self) -> str: ...

    def generate(self, company_description: str) -> OrganizationProposal: ...
