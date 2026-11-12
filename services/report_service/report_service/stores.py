"""Notification log and report registry backed by Redis (or memory for local runs/tests)."""

from __future__ import annotations

import json
import threading
from collections import deque
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4


class NotificationStore(Protocol):
    def add_notification(self, kind: str, data: dict[str, Any]) -> dict[str, Any]: ...

    def notifications(self, limit: int = 20) -> list[dict[str, Any]]: ...

    def register_report(self, task_id: str, metadata: dict[str, Any], ttl_seconds: int) -> None: ...

    def report(self, task_id: str) -> dict[str, Any] | None: ...

    def ping(self) -> bool: ...


def _notification(kind: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": uuid4().hex,
        "type": kind,
        "created_at": datetime.now(UTC).isoformat(),
        "data": data,
    }


class InMemoryStore:
    def __init__(self, max_items: int = 100) -> None:
        self._items: deque[dict[str, Any]] = deque(maxlen=max_items)
        self._reports: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def add_notification(self, kind: str, data: dict[str, Any]) -> dict[str, Any]:
        item = _notification(kind, data)
        with self._lock:
            self._items.appendleft(item)
        return item

    def notifications(self, limit: int = 20) -> list[dict[str, Any]]:
        return list(self._items)[:limit]

    def register_report(self, task_id: str, metadata: dict[str, Any], ttl_seconds: int) -> None:
        self._reports[task_id] = metadata

    def report(self, task_id: str) -> dict[str, Any] | None:
        return self._reports.get(task_id)

    def ping(self) -> bool:
        return True


class RedisStore:
    NOTIFICATIONS_KEY = "joblab:notifications"
    REPORT_KEY = "joblab:report:{task_id}"

    def __init__(self, client, max_items: int = 100) -> None:
        self._redis = client
        self._max = max_items

    @classmethod
    def from_url(cls, url: str, max_items: int = 100) -> RedisStore:
        import redis

        client = redis.Redis.from_url(url, socket_timeout=3, socket_connect_timeout=3, decode_responses=True)
        return cls(client, max_items)

    def add_notification(self, kind: str, data: dict[str, Any]) -> dict[str, Any]:
        item = _notification(kind, data)
        pipe = self._redis.pipeline()
        pipe.lpush(self.NOTIFICATIONS_KEY, json.dumps(item))
        pipe.ltrim(self.NOTIFICATIONS_KEY, 0, self._max - 1)
        pipe.execute()
        return item

    def notifications(self, limit: int = 20) -> list[dict[str, Any]]:
        return [json.loads(raw) for raw in self._redis.lrange(self.NOTIFICATIONS_KEY, 0, limit - 1)]

    def register_report(self, task_id: str, metadata: dict[str, Any], ttl_seconds: int) -> None:
        self._redis.set(self.REPORT_KEY.format(task_id=task_id), json.dumps(metadata), ex=ttl_seconds)

    def report(self, task_id: str) -> dict[str, Any] | None:
        raw = self._redis.get(self.REPORT_KEY.format(task_id=task_id))
        return json.loads(raw) if raw else None

    def ping(self) -> bool:
        try:
            return bool(self._redis.ping())
        except Exception:  # noqa: BLE001 - reported by the health check
            return False


_stores: dict[str, NotificationStore] = {}
_lock = threading.Lock()


def get_store(url: str, max_items: int = 100) -> NotificationStore:
    """One store per URL and process, so the API and eager tasks share memory stores."""
    with _lock:
        if url not in _stores:
            _stores[url] = (
                InMemoryStore(max_items) if url.startswith("memory://") else RedisStore.from_url(url, max_items)
            )
        return _stores[url]
