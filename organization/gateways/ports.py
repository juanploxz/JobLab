"""Ports consumed by the presentation layer."""

from __future__ import annotations

from typing import Any, Protocol

from organization.dtos import PlanDetailDTO, PlanPageDTO


class PlanGateway(Protocol):
    name: str

    def generate_plan(self, company_description: str) -> int: ...

    def get_plan(self, plan_id: int) -> PlanDetailDTO: ...

    def list_plans(self, page: int, page_size: int) -> PlanPageDTO: ...


class IntegrationGateway(Protocol):
    def convert_salaries(self, target: str, vacancies: list[dict[str, Any]]) -> dict[str, Any]: ...

    def ally_catalog(self) -> dict[str, Any]: ...


class ReportGateway(Protocol):
    def request_report(self, plan_id: int, report_format: str) -> dict[str, Any]: ...

    def report_status(self, task_id: str) -> dict[str, Any]: ...

    def download(self, task_id: str) -> tuple[bytes, str, str]: ...

    def notifications(self, limit: int = 20) -> list[dict[str, Any]]: ...
