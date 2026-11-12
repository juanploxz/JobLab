"""Small HTTP concerns shared by the HTML site and the public API."""

from __future__ import annotations

import re
from uuid import uuid4

from organization.request_context import reset_request_id, set_request_id

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class RequestContextMiddleware:
    """Propagate a safe correlation id and advertise the API contract version."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        candidate = request.headers.get("X-Request-ID", "").strip()
        request.request_id = (
            candidate if REQUEST_ID_PATTERN.fullmatch(candidate) else uuid4().hex
        )
        token = set_request_id(request.request_id)
        try:
            response = self.get_response(request)
        finally:
            reset_request_id(token)
        response["X-Request-ID"] = request.request_id
        if request.path.startswith("/api/v1/"):
            response["X-API-Version"] = "v1"
            response["Link"] = '</api/v2/plans/>; rel="successor-version"'
        return response
