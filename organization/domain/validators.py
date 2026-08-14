import re

from organization.domain.exceptions import DomainValidationError

MIN_DESCRIPTION_LENGTH = 80
MAX_DESCRIPTION_LENGTH = 5000

_PROMPT_INJECTION_PATTERNS = (
    re.compile(r"\b(?:ignore|ignora)\b.{0,50}\b(?:instructions|instrucciones)\b", re.I | re.S),
    re.compile(r"\b(?:system prompt|prompt del sistema|preprompt)\b", re.I),
    re.compile(r"\b(?:reveal|muestra|revela)\b.{0,40}\b(?:prompt|instructions|instrucciones)\b", re.I | re.S),
)


def validate_company_description(value: str) -> str:
    """Normalize and validate the untrusted company description."""
    normalized = " ".join((value or "").split())
    if len(normalized) < MIN_DESCRIPTION_LENGTH:
        raise DomainValidationError(
            f"Describe la empresa con al menos {MIN_DESCRIPTION_LENGTH} caracteres."
        )
    if len(normalized) > MAX_DESCRIPTION_LENGTH:
        raise DomainValidationError(
            f"La descripcion no puede superar {MAX_DESCRIPTION_LENGTH} caracteres."
        )
    if any(pattern.search(normalized) for pattern in _PROMPT_INJECTION_PATTERNS):
        raise DomainValidationError(
            "La descripcion contiene instrucciones dirigidas al sistema. "
            "Incluye solamente informacion sobre la empresa."
        )
    return normalized
