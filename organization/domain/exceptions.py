class DomainValidationError(ValueError):
    """Raised when untrusted input violates a business rule."""


class ProposalParsingError(DomainValidationError):
    """Raised when an AI response cannot become a valid proposal."""


class GenerationError(RuntimeError):
    """Safe application error shown when a generation request fails."""
