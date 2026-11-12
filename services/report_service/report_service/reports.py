"""Report renderers (Strategy) selected by ``ReportRendererFactory`` (Factory Method)."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from report_service.i18n import translate


@dataclass(frozen=True, slots=True)
class RenderedReport:
    filename: str
    content_type: str
    content: str


class ReportRenderer(Protocol):
    format: str

    def render(
        self, plan: dict[str, Any], usd: dict[Any, dict[str, str]], language: str
    ) -> RenderedReport: ...


class CsvReportRenderer:
    format = "csv"

    def render(self, plan, usd, language):
        t = lambda message: translate(language, message)  # noqa: E731
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        metrics = plan.get("metrics", {})
        writer.writerow([t("Reporte de plan organizacional"), plan["company_name"]])
        writer.writerow([t("Plan"), plan["id"]])
        writer.writerow([t("Generado"), datetime.now(UTC).isoformat()])
        writer.writerow([t("Áreas"), metrics.get("department_count", 0)])
        writer.writerow([t("Tipos de vacante"), metrics.get("vacancy_count", 0)])
        writer.writerow([t("Puestos sugeridos"), metrics.get("total_positions", 0)])
        writer.writerow([])
        writer.writerow(
            [
                t("Departamento"),
                t("Vacante"),
                t("Puestos"),
                t("Salario mínimo"),
                t("Salario máximo"),
                t("Moneda"),
                t("Periodicidad"),
                t("Salario mínimo (USD)"),
                t("Salario máximo (USD)"),
                t("Conocimientos"),
                t("Reporta a"),
            ]
        )
        for vacancy in plan.get("vacancies", []):
            converted = usd.get(vacancy["id"], {})
            writer.writerow(
                [
                    vacancy["department_name"],
                    vacancy["name"],
                    vacancy["available_positions"],
                    vacancy["salary_min"],
                    vacancy["salary_max"],
                    vacancy["currency"],
                    vacancy["salary_period"],
                    converted.get("salary_min", ""),
                    converted.get("salary_max", ""),
                    "; ".join(vacancy.get("required_knowledge", [])),
                    vacancy.get("reports_to", ""),
                ]
            )
        return RenderedReport(
            filename=f"joblab-plan-{plan['id']}.csv",
            content_type="text/csv; charset=utf-8",
            content="\ufeff" + buffer.getvalue(),
        )


class JsonReportRenderer:
    format = "json"

    def render(self, plan, usd, language):
        vacancies = [
            {**vacancy, "salary_usd": usd.get(vacancy["id"]) or None}
            for vacancy in plan.get("vacancies", [])
        ]
        document = {
            "title": translate(language, "Reporte de plan organizacional"),
            "generated_at": datetime.now(UTC).isoformat(),
            "plan": {**plan, "vacancies": vacancies},
        }
        return RenderedReport(
            filename=f"joblab-plan-{plan['id']}.json",
            content_type="application/json",
            content=json.dumps(document, ensure_ascii=False, indent=2),
        )


class ReportRendererFactory:
    _renderers: dict[str, type] = {"csv": CsvReportRenderer, "json": JsonReportRenderer}

    @classmethod
    def formats(cls) -> tuple[str, ...]:
        return tuple(cls._renderers)

    @classmethod
    def create(cls, report_format: str) -> ReportRenderer:
        try:
            return cls._renderers[report_format.lower()]()
        except KeyError as exc:
            raise ValueError(report_format) from exc
