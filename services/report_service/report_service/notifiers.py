"""Notification channels (Factory selects e-mail or log based on configuration)."""

from __future__ import annotations

import logging
import smtplib
from collections.abc import Mapping
from email.message import EmailMessage
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class Notifier(Protocol):
    channel: str

    def send(self, subject: str, body: str) -> None: ...


class LogNotifier:
    channel = "log"

    def send(self, subject: str, body: str) -> None:
        logger.info("NOTIFICATION | %s | %s", subject, body)


class EmailNotifier:
    channel = "email"

    def __init__(self, config: Mapping[str, Any], smtp_factory=smtplib.SMTP) -> None:
        self._config = config
        self._smtp_factory = smtp_factory

    def send(self, subject: str, body: str) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self._config["NOTIFY_EMAIL_FROM"]
        message["To"] = self._config["NOTIFY_EMAIL_TO"]
        message.set_content(body)
        with self._smtp_factory(self._config["SMTP_HOST"], self._config["SMTP_PORT"], timeout=10) as smtp:
            if self._config["SMTP_USE_TLS"]:
                smtp.starttls()
            if self._config["SMTP_USER"]:
                smtp.login(self._config["SMTP_USER"], self._config["SMTP_PASSWORD"])
            smtp.send_message(message)


def build_notifier(config: Mapping[str, Any]) -> Notifier:
    if config.get("SMTP_HOST") and config.get("NOTIFY_EMAIL_TO"):
        return EmailNotifier(config)
    return LogNotifier()
