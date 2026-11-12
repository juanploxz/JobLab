"""HTTP client with timeouts, bounded retries, a circuit breaker and context propagation."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from organization.domain.exceptions import ServiceUnavailableError


class CircuitBreaker:
    """Closed -> Open after N consecutive failures; Half-open after ``reset_seconds``."""

    CLOSED, OPEN, HALF_OPEN = "closed", "open", "half_open"

    def __init__(
        self,
        failure_threshold: int = 3,
        reset_seconds: float = 30,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.failure_threshold = max(1, failure_threshold)
        self.reset_seconds = reset_seconds
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        if self._opened_at is None:
            return self.CLOSED
        if self._clock() - self._opened_at >= self.reset_seconds:
            return self.HALF_OPEN
        return self.OPEN

    def allow(self) -> bool:
        return self.state != self.OPEN

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold or self._opened_at is not None:
                self._opened_at = self._clock()


class ServiceClient:
    """JSON client for one microservice. 5xx answers and network errors count as failures."""

    def __init__(
        self,
        service: str,
        base_url: str,
        *,
        timeout: float = 5,
        breaker: CircuitBreaker | None = None,
        session: requests.Session | None = None,
        context: Callable[[], dict[str, str]] | None = None,
    ) -> None:
        self.service = service
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.breaker = breaker or CircuitBreaker()
        self._session = session or _session_with_retries()
        self._context = context or (lambda: {})

    def request(
        self, method: str, path: str, *, passthrough: tuple[int, ...] = (), **kwargs: Any
    ) -> requests.Response:
        """``passthrough`` lists 5xx codes that are business answers, not service failures."""
        if not self.breaker.allow():
            raise ServiceUnavailableError(self.service, "circuit open")
        headers = {"Accept": "application/json", **self._context(), **kwargs.pop("headers", {})}
        try:
            response = self._session.request(
                method, f"{self.base_url}{path}", timeout=self.timeout, headers=headers, **kwargs
            )
        except requests.RequestException as exc:
            self.breaker.record_failure()
            raise ServiceUnavailableError(self.service, str(exc)) from exc
        if response.status_code >= 500 and response.status_code not in passthrough:
            self.breaker.record_failure()
            raise ServiceUnavailableError(self.service, f"HTTP {response.status_code}")
        self.breaker.record_success()
        return response


def _session_with_retries() -> requests.Session:
    retry = Retry(
        total=2,
        backoff_factor=0.3,
        status_forcelist=(502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def error_detail(response: requests.Response, default: str) -> tuple[str, str]:
    try:
        error = response.json().get("error", {})
        return str(error.get("code", "")), str(error.get("detail") or default)
    except (ValueError, AttributeError):
        return "", default
