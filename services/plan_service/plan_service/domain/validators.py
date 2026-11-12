"""Business limits and validation of untrusted input (migrated from Django)."""

from __future__ import annotations

import re

from plan_service.domain.exceptions import DomainValidationError
from plan_service.i18n import _

MIN_DESCRIPTION_LENGTH = 80
MAX_DESCRIPTION_LENGTH = 5000
MIN_COMPANY_NAME_LENGTH = 3
MIN_COMPANY_SUMMARY_LENGTH = 40
MAX_COMPANY_SUMMARY_LENGTH = 2000
MAX_ASSUMPTIONS = 20
MIN_ASSUMPTION_LENGTH = 2
MAX_ASSUMPTION_LENGTH = 500
MIN_UNIT_NAME_LENGTH = 2
MIN_UNIT_DESCRIPTION_LENGTH = 30
MAX_UNIT_DESCRIPTION_LENGTH = 1000
MIN_VACANCY_NAME_LENGTH = 3
MAX_VACANCY_NAME_LENGTH = 140
MIN_VACANCY_DESCRIPTION_LENGTH = 50
MAX_VACANCY_DESCRIPTION_LENGTH = 2000
MIN_AVAILABLE_POSITIONS = 1
MAX_AVAILABLE_POSITIONS = 500
MIN_KNOWLEDGE_LENGTH = 2
MAX_KNOWLEDGE_LENGTH = 120
MAX_REQUIRED_KNOWLEDGE = 20
MAX_REPORTS_TO_LENGTH = 140

CURRENCIES = ("COP", "USD", "EUR", "MXN")
SALARY_PERIODS = ("HOURLY", "MONTHLY", "ANNUAL")

_PROMPT_INJECTION_PATTERNS = (
    re.compile(
        r"\b(?:ignore|ignora)\b.{0,50}\b(?:instructions|instrucciones)\b",
        re.I | re.S,
    ),
    re.compile(r"\b(?:system prompt|prompt del sistema|preprompt)\b", re.I),
    re.compile(
        r"\b(?:reveal|muestra|revela)\b.{0,40}"
        r"\b(?:prompt|instructions|instrucciones)\b",
        re.I | re.S,
    ),
)


def normalize_spaces(value: str) -> str:
    return " ".join((value or "").split())


def validate_company_description(value: object) -> str:
    """Normalize and validate the untrusted company description."""
    if not isinstance(value, str):
        raise DomainValidationError(_("La descripción de la empresa debe ser texto."))
    normalized = normalize_spaces(value)
    if len(normalized) < MIN_DESCRIPTION_LENGTH:
        raise DomainValidationError(
            _(
                "Describe la empresa con al menos %(minimum)s caracteres.",
                minimum=MIN_DESCRIPTION_LENGTH,
            )
        )
    if len(normalized) > MAX_DESCRIPTION_LENGTH:
        raise DomainValidationError(
            _(
                "La descripción no puede superar %(maximum)s caracteres.",
                maximum=MAX_DESCRIPTION_LENGTH,
            )
        )
    if any(pattern.search(normalized) for pattern in _PROMPT_INJECTION_PATTERNS):
        raise DomainValidationError(
            _(
                "La descripción contiene instrucciones dirigidas al sistema. "
                "Incluye solamente información sobre la empresa."
            )
        )
    return normalized
