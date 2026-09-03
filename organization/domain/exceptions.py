class DomainValidationError(ValueError):
    """Raised when untrusted input violates a business rule."""


class ProposalParsingError(DomainValidationError):
    """Raised when an AI response cannot become a valid proposal."""


class GenerationError(RuntimeError):
    """Safe application error shown when a generation request fails."""


class ResourceNotFoundError(LookupError):
    """Raised by an application service when a requested resource does not exist."""

    default_code = "resource_not_found"

    def __init__(self, detail: str, *, code: str | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code or self.default_code


class ResourceConflictError(RuntimeError):
    """Raised when a valid command conflicts with persisted application state."""

    default_code = "resource_conflict"

    def __init__(self, detail: str, *, code: str | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code or self.default_code
