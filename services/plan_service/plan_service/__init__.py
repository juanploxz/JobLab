"""JobLab plan microservice: organizational plans, units and vacancies.

This bounded context was extracted from the Django monolith with the Strangler
pattern. It owns its database and publishes integration events to Redis.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any
from uuid import uuid4

from flask import Flask, g, request
from flask_babel import get_locale
from werkzeug.middleware.proxy_fix import ProxyFix

from plan_service.api.errors import register_error_handlers
from plan_service.api.routes import (
    build_plans_blueprint,
    ops_blueprint,
    public_blueprint,
    strangler_blueprint,
)
from plan_service.bootstrap import EVENT_PUBLISHER_KEY
from plan_service.config import Config
from plan_service.extensions import babel, db
from plan_service.i18n import select_locale
from plan_service.infra.events import build_event_publisher

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def create_app(overrides: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)
    app.json.sort_keys = False
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    db.init_app(app)
    babel.init_app(app, locale_selector=select_locale)

    publisher = app.config.get("EVENT_PUBLISHER") or build_event_publisher(
        app.config["CELERY_BROKER_URL"]
    )
    app.extensions[EVENT_PUBLISHER_KEY] = publisher

    app.register_blueprint(ops_blueprint)
    app.register_blueprint(build_plans_blueprint("plans_v2"), url_prefix="/api/v2")
    app.register_blueprint(build_plans_blueprint("plans_v1"), url_prefix="/api/v1")
    app.register_blueprint(public_blueprint, url_prefix="/api/v2/public")
    app.register_blueprint(strangler_blueprint, url_prefix="/api/v2")
    register_error_handlers(app)

    @app.before_request
    def _request_context() -> None:
        candidate = request.headers.get("X-Request-ID", "").strip()
        g.request_id = candidate if REQUEST_ID_PATTERN.fullmatch(candidate) else uuid4().hex

    @app.after_request
    def _response_headers(response):
        response.headers["X-Request-ID"] = getattr(g, "request_id", uuid4().hex)
        response.headers["X-Service"] = app.config["SERVICE_NAME"]
        response.headers["Content-Language"] = str(get_locale())
        if request.path.startswith("/api/v1/"):
            response.headers["X-API-Version"] = "v1"
            response.headers["Link"] = '</api/v2/plans/>; rel="successor-version"'
        elif request.path.startswith("/api/v2/"):
            response.headers["X-API-Version"] = "v2"
        return response

    if app.config["AUTO_CREATE_SCHEMA"]:
        with app.app_context():
            from plan_service import models  # noqa: F401 - register tables

            db.create_all()
    return app
