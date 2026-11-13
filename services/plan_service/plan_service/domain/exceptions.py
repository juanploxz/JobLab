class DomainValidationError(ValueError):
    """Raised when untrusted input violates a business rule."""


class ProposalParsingError(DomainValidationError):
    """Raised when an AI response cannot become a valid proposal."""


class GenerationError(RuntimeError):
    """Safe application error raised when a generation request fails."""


class GenerationUnavailableError(GenerationError):
    """The AI provider failed (network, timeout, rejected request or invalid output)."""


class ConfigurationError(RuntimeError):
    """Raised when infrastructure is selected with an invalid configuration."""


class ResourceNotFoundError(LookupError):
    default_code = "resource_not_found"

    def __init__(self, detail: str, *, code: str | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code or self.default_code


class ResourceConflictError(RuntimeError):
    default_code = "resource_conflict"

    def __init__(self, detail: str, *, code: str | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code or self.default_code
