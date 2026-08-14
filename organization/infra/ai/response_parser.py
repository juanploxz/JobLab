from pydantic import ValidationError

from organization.domain.exceptions import ProposalParsingError
from organization.domain.schemas import OrganizationProposal


class OrganizationResponseParser:
    """Convert strict JSON into a validated provider-independent proposal."""

    def parse(self, raw_response: str) -> OrganizationProposal:
        if not raw_response or not raw_response.strip():
            raise ProposalParsingError("El proveedor de IA devolvio una respuesta vacia")
        if raw_response.lstrip().startswith("```"):
            raise ProposalParsingError("La respuesta contiene Markdown en lugar de JSON puro")
        try:
            return OrganizationProposal.model_validate_json(raw_response)
        except ValidationError as exc:
            errors = "; ".join(
                f"{'.'.join(map(str, item['loc']))}: {item['msg']}"
                for item in exc.errors(include_url=False)[:8]
            )
            raise ProposalParsingError(f"La propuesta de IA no es valida: {errors}") from exc
