"""JobLab integration microservice: third-party exchange rates and the allied team's API."""

from __future__ import annotations

import logging
import os
import re
from typing import Any
from uuid import uuid4

from flask import Flask, g, request
from flask_babel import Babel, get_locale
from werkzeug.middleware.proxy_fix import ProxyFix

from integration_service.bootstrap import build_ally_catalog, build_exchange_provider
from integration_service.config import Config
from integration_service.i18n import select_locale
from integration_service.routes import ALLY_KEY, EXCHANGE_KEY, api, ops, register_error_handlers

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def create_app(overrides: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)
    app.json.sort_keys = False
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    Babel(app, locale_selector=select_locale)

    app.extensions[EXCHANGE_KEY] = app.config.get("EXCHANGE_PROVIDER") or build_exchange_provider(app.config)
    app.extensions[ALLY_KEY] = app.config.get("ALLY_CATALOG") or build_ally_catalog(app.config)

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
