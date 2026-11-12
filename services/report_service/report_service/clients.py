"""HTTP clients for the services the worker depends on (plan and integration services)."""

from __future__ import annotations

from typing import Any

import requests


class PlanNotFound(LookupError):
    """The plan does not exist: retrying would never succeed."""


class UpstreamUnavailable(RuntimeError):
    """Transient failure: the Celery task retries with exponential backoff."""


class PlanServiceClient:
    def __init__(self, base_url: str, timeout: float, session: requests.Session | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = session or requests.Session()

    def get_plan(self, plan_id: int, language: str = "es") -> dict[str, Any]:
        url = f"{self._base_url}/api/v2/plans/{int(plan_id)}/"
        try:
            response = self._session.get(url, timeout=self._timeout, headers={"Accept-Language": language})
        except requests.RequestException as exc:
            raise UpstreamUnavailable(str(exc)) from exc
        if response.status_code == 404:
            raise PlanNotFound(plan_id)
        if response.status_code >= 500:
            raise UpstreamUnavailable(f"plan-service answered {response.status_code}")
        response.raise_for_status()
        return response.json()


class SalaryConversionClient:
    """Optional enrichment: failures degrade the report instead of failing it."""

    def __init__(self, base_url: str, timeout: float, session: requests.Session | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = session or requests.Session()

    def to_usd(self, vacancies: list[dict[str, Any]]) -> dict[Any, dict[str, str]]:
        if not self._base_url or not vacancies:
            return {}
        items = [
            {
                "id": vacancy["id"],
                "salary_min": vacancy["salary_min"],
                "salary_max": vacancy["salary_max"],
                "currency": vacancy["currency"],
            }
            for vacancy in vacancies
        ]
        try:
            response = self._session.post(
                f"{self._base_url}/api/v2/salaries/convert/",
                json={"target": "USD", "items": items},
                timeout=self._timeout,
            )
            response.raise_for_status()
            return {item["id"]: item for item in response.json().get("items", [])}
        except (requests.RequestException, ValueError, KeyError, TypeError):
            return {}
