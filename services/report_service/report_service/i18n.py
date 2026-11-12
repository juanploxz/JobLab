"""gettext for both contexts: Flask requests (Flask-Babel) and Celery tasks (stdlib gettext)."""

from __future__ import annotations

import gettext as stdlib_gettext
from functools import lru_cache
from pathlib import Path

from flask import current_app, has_app_context, has_request_context, request
from flask_babel import gettext as babel_gettext

TRANSLATIONS_DIR = Path(__file__).resolve().parent / "translations"
SUPPORTED = ("es", "en")


def _(message: str, **variables: object) -> str:
    if has_app_context():
        return babel_gettext(message, **variables)
    return message % variables if variables else message


@lru_cache(maxsize=4)
def translator(language: str) -> stdlib_gettext.NullTranslations:
    language = language if language in SUPPORTED else "es"
    return stdlib_gettext.translation(
        "messages", localedir=TRANSLATIONS_DIR, languages=[language], fallback=True
    )


def translate(language: str, message: str, **variables: object) -> str:
    text = translator(language).gettext(message)
    return text % variables if variables else text


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
