"""JobLab report microservice: asynchronous reports and notifications with Celery + Redis."""

from __future__ import annotations

import logging
import os
import re
from typing import Any
from uuid import uuid4

from flask import Flask, g, request
from flask_babel import Babel, get_locale
from werkzeug.middleware.proxy_fix import ProxyFix

from report_service import celery_app
from report_service.config import Config
from report_service.i18n import select_locale

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def create_app(overrides: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)
    celery_app.configure({key: value for key, value in app.config.items() if key.isupper()})

    from report_service.routes import api, ops, register_error_handlers

    app.json.sort_keys = False
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    Babel(app, locale_selector=select_locale)

    app.register_blueprint(ops)
    app.register_blueprint(api, url_prefix="/api/v2")
    register_error_handlers(app)

    @app.before_request
    def _request_context() -> None:
        candidate = request.headers.get("X-Request-ID", "").strip()
        g.request_id = candidate if REQUEST_ID_PATTERN.fullmatch(candidate) else uuid4().hex

    @app.after_request
    def _headers(response):
        response.headers["X-Request-ID"] = getattr(g, "request_id", uuid4().hex)
        response.headers["X-Service"] = app.config["SERVICE_NAME"]
        response.headers["Content-Language"] = str(get_locale())
        if request.path.startswith("/api/v2/"):
            response.headers["X-API-Version"] = "v2"
        return response

    return app
