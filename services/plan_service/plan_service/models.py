"""Persistence model owned exclusively by the plan microservice (database per service)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from plan_service.extensions import db


def utcnow() -> datetime:
    return datetime.now(UTC)


class GenerationRequest(db.Model):
    __tablename__ = "generation_requests"

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=PENDING)
    provider_name: Mapped[str] = mapped_column(String(20), default="MOCK")
    prompt_version: Mapped[str] = mapped_column(String(20), default="v1")
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    plan: Mapped[Plan | None] = relationship(back_populates="request", uselist=False)


class Plan(db.Model):
    __tablename__ = "plans"

    DRAFT = "DRAFT"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("generation_requests.id", ondelete="CASCADE"), unique=True
    )
    company_name: Mapped[str] = mapped_column(String(160))
    company_summary: Mapped[str] = mapped_column(Text)
    assumptions: Mapped[list] = mapped_column(JSON, default=list)
    review_status: Mapped[str] = mapped_column(String(16), default=DRAFT)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    request: Mapped[GenerationRequest] = relationship(back_populates="plan")
    units: Mapped[list[Unit]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="Unit.name"
    )
    vacancies: Mapped[list[Vacancy]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="Vacancy.name"
    )


class Unit(db.Model):
    __tablename__ = "organizational_units"
    __table_args__ = (
        UniqueConstraint("plan_id", "code", name="unique_unit_code_per_plan"),
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="unit_cannot_be_own_parent"),
        Index(
            "unique_root_unit_per_plan",
            "plan_id",
            unique=True,
            sqlite_where=db.text("parent_id IS NULL"),
            postgresql_where=db.text("parent_id IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizational_units.id"), nullable=True
    )

    plan: Mapped[Plan] = relationship(back_populates="units")
    parent: Mapped[Unit | None] = relationship(remote_side=[id])


class Vacancy(db.Model):
    __tablename__ = "vacancies"
    __table_args__ = (
        UniqueConstraint(
            "plan_id", "department_id", "name_key", name="unique_vacancy_name_ci_per_department"
        ),
        CheckConstraint("available_positions >= 1", name="vacancy_positions_at_least_one"),
        CheckConstraint("available_positions <= 500", name="vacancy_positions_at_most_500"),
        CheckConstraint("salary_min >= 0", name="vacancy_salary_min_non_negative"),
        CheckConstraint("salary_max >= salary_min", name="vacancy_salary_range_valid"),
    )

    DRAFT = "DRAFT"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("organizational_units.id"))
    name: Mapped[str] = mapped_column(String(140))
    name_key: Mapped[str] = mapped_column(String(140))
    available_positions: Mapped[int] = mapped_column(Integer)
    salary_min: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    salary_max: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="COP")
    salary_period: Mapped[str] = mapped_column(String(10), default="MONTHLY")
    description: Mapped[str] = mapped_column(Text)
    required_knowledge: Mapped[list] = mapped_column(JSON, default=list)
    reports_to: Mapped[str] = mapped_column(String(140), default="")
    status: Mapped[str] = mapped_column(String(12), default=DRAFT)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    plan: Mapped[Plan] = relationship(back_populates="vacancies")
    department: Mapped[Unit] = relationship()
