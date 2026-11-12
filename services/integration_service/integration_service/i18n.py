"""gettext helpers shared by every layer of the integration microservice."""

from __future__ import annotations

from flask import current_app, has_app_context, has_request_context, request
from flask_babel import gettext as babel_gettext


def _(message: str, **variables: object) -> str:
    if has_app_context():
        return babel_gettext(message, **variables)
    return message % variables if variables else message


def select_locale() -> str:
    supported = current_app.config["SUPPORTED_LOCALES"]
    if has_request_context():
        explicit = (request.args.get("lang") or "").strip().lower()
        if explicit in supported:
            return explicit
        best = request.accept_languages.best_match(supported)
        if best:
            return best
    return current_app.config["BABEL_DEFAULT_LOCALE"]
