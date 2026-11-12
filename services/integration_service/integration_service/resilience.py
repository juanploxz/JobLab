"""Resilience primitives for outbound HTTP calls: timeouts, retries and a circuit breaker."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import TypeVar

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

T = TypeVar("T")


class CircuitOpenError(RuntimeError):
    """Raised without calling the dependency while the circuit is open."""


class CircuitBreaker:
    """Closed -> Open after N consecutive failures; Half-open after ``reset_seconds``."""

    CLOSED, OPEN, HALF_OPEN = "closed", "open", "half_open"

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        reset_seconds: float = 30,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.name = name
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

    def call(self, operation: Callable[[], T]) -> T:
        if self.state == self.OPEN:
            raise CircuitOpenError(f"circuit {self.name} is open")
        try:
            result = operation()
        except Exception:
            with self._lock:
                self._failures += 1
                if self._failures >= self.failure_threshold or self._opened_at is not None:
                    self._opened_at = self._clock()
            raise
        with self._lock:
            self._failures = 0
            self._opened_at = None
        return result


def build_http_session(retries: int = 2, backoff: float = 0.3) -> requests.Session:
    """Session with bounded retries (exponential backoff) for idempotent GET requests."""
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        backoff_factor=backoff,
        status_forcelist=(429, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry, pool_maxsize=10)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers["User-Agent"] = "JobLab-integration-service/2.0"
    return session
