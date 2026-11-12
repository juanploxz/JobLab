from pydantic import ValidationError

from plan_service.domain.exceptions import ProposalParsingError
from plan_service.domain.schemas import OrganizationProposal


class OrganizationResponseParser:
    """Convert strict JSON text into a validated provider-independent proposal."""

    def parse(self, raw_response: str) -> OrganizationProposal:
        if not raw_response or not raw_response.strip():
            raise ProposalParsingError("empty AI response")
        if raw_response.lstrip().startswith("```"):
            raise ProposalParsingError("AI response contains Markdown instead of JSON")
        try:
            return OrganizationProposal.model_validate_json(raw_response)
        except ValidationError as exc:
            errors = "; ".join(
                f"{'.'.join(map(str, item['loc']))}: {item['msg']}"
                for item in exc.errors(include_url=False)[:8]
            )
            raise ProposalParsingError(f"invalid AI proposal: {errors}") from exc
