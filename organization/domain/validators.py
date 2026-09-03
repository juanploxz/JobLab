import re

from django.core.exceptions import ValidationError

from organization.domain.exceptions import DomainValidationError

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
MIN_VACANCY_DESCRIPTION_LENGTH = 50
MAX_VACANCY_DESCRIPTION_LENGTH = 2000
MIN_AVAILABLE_POSITIONS = 1
MAX_AVAILABLE_POSITIONS = 500
MIN_KNOWLEDGE_LENGTH = 2
MAX_KNOWLEDGE_LENGTH = 120
MAX_REQUIRED_KNOWLEDGE = 20

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


def validate_company_description_field(value: str) -> None:
    """Adapt the domain validation error to Django's declarative validator API."""
    try:
        validate_company_description(value)
    except DomainValidationError as exc:
        raise ValidationError(str(exc), code="invalid_company_description") from exc


def _validate_string_list(
    value: object,
    *,
    label: str,
    allow_empty: bool,
    max_items: int,
    min_item_length: int,
    max_item_length: int,
    require_unique: bool = False,
) -> None:
    if not isinstance(value, list):
        raise ValidationError(f"{label} debe ser una lista.", code="invalid_list")
    if not allow_empty and not value:
        raise ValidationError(
            f"{label} debe contener al menos un elemento.",
            code="empty_list",
        )
    if len(value) > max_items:
        raise ValidationError(
            f"{label} no puede contener mas de {max_items} elementos.",
            code="too_many_items",
        )

    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            raise ValidationError(
                f"Cada elemento de {label.lower()} debe ser texto.",
                code="invalid_item_type",
            )
        normalized = " ".join(item.split())
        if not min_item_length <= len(normalized) <= max_item_length:
            raise ValidationError(
                f"Cada elemento de {label.lower()} debe tener entre "
                f"{min_item_length} y {max_item_length} caracteres.",
                code="invalid_item_length",
            )
        key = normalized.casefold()
        if require_unique and key in seen:
            raise ValidationError(
                f"{label} no puede contener elementos duplicados.",
                code="duplicate_items",
            )
        seen.add(key)


def validate_assumptions(value: object) -> None:
    _validate_string_list(
        value,
        label="Supuestos",
        allow_empty=True,
        max_items=MAX_ASSUMPTIONS,
        min_item_length=MIN_ASSUMPTION_LENGTH,
        max_item_length=MAX_ASSUMPTION_LENGTH,
    )


def validate_required_knowledge(value: object) -> None:
    _validate_string_list(
        value,
        label="Conocimientos requeridos",
        allow_empty=False,
        max_items=MAX_REQUIRED_KNOWLEDGE,
        min_item_length=MIN_KNOWLEDGE_LENGTH,
        max_item_length=MAX_KNOWLEDGE_LENGTH,
        require_unique=True,
    )
