"""Outbound e-mail delivery.

Only a small, well defined surface is available to the application: the
verification and password-reset mails.  Recipient addresses are validated and
never taken from a raw HTTP header, which prevents header injection.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr, parseaddr
from typing import Optional

from ..security import is_valid_email
from ..settings import Settings, get_settings

logger = logging.getLogger(__name__)


class MailError(RuntimeError):
    """Raised when a message could not be delivered."""


class Mailer:
    """Base mailer interface."""

    def send(self, recipient: str, subject: str, body: str) -> bool:
        raise NotImplementedError

    @staticmethod
    def _validate(recipient: str) -> str:
        recipient = (recipient or "").strip()
        if not is_valid_email(recipient):
            raise MailError("invalid recipient address")
        return recipient


class NullMailer(Mailer):
    """Drops every message (used in tests and air-gapped deployments)."""

    def send(self, recipient: str, subject: str, body: str) -> bool:
        logger.info("mail suppressed", extra={"recipient": recipient, "subject": subject})
        return True


class ConsoleMailer(Mailer):
    """Writes the message to the log (development only)."""

    def send(self, recipient: str, subject: str, body: str) -> bool:
        recipient = self._validate(recipient)
        logger.info("outgoing mail (console backend)", extra={"recipient": recipient, "subject": subject})
        logger.debug("mail body: %s", body)
        return True


class SmtpMailer(Mailer):
    """Sends mail through an SMTP server."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.smtp_host:
            raise MailError("no SMTP host configured")

    def send(self, recipient: str, subject: str, body: str) -> bool:
        recipient = self._validate(recipient)
        settings = self.settings
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = formataddr(("Owner-Only AI Camera Assistant", settings.mailer_from))
        message["To"] = recipient
        message.set_content(body)
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
                if settings.smtp_use_tls:
                    server.starttls()
                if settings.smtp_username:
                    password = settings.smtp_password.get_secret_value() if settings.smtp_password else ""
                    server.login(settings.smtp_username, password)
                server.send_message(message)
        except (smtplib.SMTPException, OSError) as exc:
            logger.warning("mail delivery failed", extra={"error_type": type(exc).__name__})
            raise MailError("the message could not be delivered") from exc
        return True


def build_mailer(settings: Optional[Settings] = None) -> Mailer:
    """Instantiate the configured mailer."""
    settings = settings or get_settings()
    if settings.mailer_backend == "smtp":
        try:
            return SmtpMailer(settings)
        except MailError:
            logger.warning("SMTP mailer unavailable, falling back to the console backend")
            return ConsoleMailer()
    if settings.mailer_backend == "null":
        return NullMailer()
    return ConsoleMailer()


def safe_display_name(address: str) -> str:
    """Return a display name without the address part."""
    name, _ = parseaddr(address)
    return name or address
