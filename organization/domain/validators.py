import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

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
            _("Describe la empresa con al menos %(minimum)s caracteres.") % {"minimum": MIN_DESCRIPTION_LENGTH}
        )
    if len(normalized) > MAX_DESCRIPTION_LENGTH:
        raise DomainValidationError(
            _("La descripcion no puede superar %(maximum)s caracteres.") % {"maximum": MAX_DESCRIPTION_LENGTH}
        )
    if any(pattern.search(normalized) for pattern in _PROMPT_INJECTION_PATTERNS):
        raise DomainValidationError(
            _(
                "La descripcion contiene instrucciones dirigidas al sistema. "
                "Incluye solamente informacion sobre la empresa."
            )
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
        raise ValidationError(_("%(label)s debe ser una lista.") % {"label": label}, code="invalid_list")
    if not allow_empty and not value:
        raise ValidationError(
            _("%(label)s debe contener al menos un elemento.") % {"label": label},
            code="empty_list",
        )
    if len(value) > max_items:
        raise ValidationError(
            _("%(label)s no puede contener mas de %(maximum)s elementos.") % {"label": label, "maximum": max_items},
            code="too_many_items",
        )

    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            raise ValidationError(
                _("Cada elemento de %(label)s debe ser texto.") % {"label": label.lower()},
                code="invalid_item_type",
            )
        normalized = " ".join(item.split())
        if not min_item_length <= len(normalized) <= max_item_length:
            raise ValidationError(
                _("Cada elemento de %(label)s debe tener entre %(minimum)s y %(maximum)s caracteres.")
                % {"label": label.lower(), "minimum": min_item_length, "maximum": max_item_length},
                code="invalid_item_length",
            )
        key = normalized.casefold()
        if require_unique and key in seen:
            raise ValidationError(
                _("%(label)s no puede contener elementos duplicados.") % {"label": label},
                code="duplicate_items",
            )
        seen.add(key)


def validate_assumptions(value: object) -> None:
    _validate_string_list(
        value,
        label=_("Supuestos"),
        allow_empty=True,
        max_items=MAX_ASSUMPTIONS,
        min_item_length=MIN_ASSUMPTION_LENGTH,
        max_item_length=MAX_ASSUMPTION_LENGTH,
    )


def validate_required_knowledge(value: object) -> None:
    _validate_string_list(
        value,
        label=_("Conocimientos requeridos"),
        allow_empty=False,
        max_items=MAX_REQUIRED_KNOWLEDGE,
        min_item_length=MIN_KNOWLEDGE_LENGTH,
        max_item_length=MAX_KNOWLEDGE_LENGTH,
        require_unique=True,
    )
