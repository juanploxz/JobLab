"""Input schemas: structural validation of JSON bodies (the role DRF serializers had)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class _Input(BaseModel):
    model_config = ConfigDict(extra="ignore")


class GeneratePlanInput(_Input):
    company_description: str


class CreateVacancyInput(_Input):
    department_id: int
    name: str
    available_positions: int
    salary_min: Decimal = Field(max_digits=14, decimal_places=2)
    salary_max: Decimal = Field(max_digits=14, decimal_places=2)
    currency: str = Field(max_length=3)
    salary_period: str = Field(max_length=10)
    description: str
    required_knowledge: list[str]
    reports_to: str | None = ""


def field_errors(exc: ValidationError) -> dict[str, list[str]]:
    """Translate pydantic errors to the ``fields`` object of the error contract."""
    fields: dict[str, list[str]] = {}
    for error in exc.errors(include_url=False):
        location = ".".join(str(part) for part in error["loc"]) or "non_field_errors"
        fields.setdefault(location, []).append(error["type"])
    return fields
