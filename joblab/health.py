"""Liveness/readiness endpoint used by Docker and the Nginx gateway."""

from django.db import connection
from django.http import JsonResponse


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        database = "ok"
    except Exception:  # noqa: BLE001 - reported as degraded
        database = "unavailable"
    healthy = database == "ok"
    return JsonResponse(
        {"status": "ok" if healthy else "degraded", "service": "django", "checks": {"database": database}},
        status=200 if healthy else 503,
    )
