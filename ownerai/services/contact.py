"""Public contact form handling.

Anti-abuse measures:

* rate limiting per IP and per e-mail address,
* a honeypot field that only automated clients fill in,
* a minimum fill-in time,
* strict length and content validation,
* the e-mail address is stored encrypted and never echoed back in a way that
  could be abused for enumeration,
* no user supplied data is ever placed into an e-mail header.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Tuple

from sqlalchemy.orm import Session

from ..crypto import encrypt_bytes, hash_value
from ..models import ContactMessage
from ..security import is_valid_email

logger = logging.getLogger(__name__)

MINIMUM_FORM_SECONDS = 3
MAX_SUBMISSIONS_PER_HOUR = 3

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


class ContactRejected(ValueError):
    """Raised when a contact submission is rejected."""


def validate_submission(
    *,
    email: str,
    subject: str,
    message: str,
    honeypot: str = "",
    elapsed_seconds: float = 9999.0,
) -> Tuple[str, str, str]:
    """Validate and normalise a contact submission."""
    if honeypot:
        # Silently accept but never process - automated clients get a success
        # response so they cannot detect the honeypot.
        raise ContactRejected("automated submission")
    if elapsed_seconds < MINIMUM_FORM_SECONDS:
        raise ContactRejected("submitted too quickly")

    email = (email or "").strip()
    subject = _CONTROL_CHARS.sub("", (subject or "").strip())
    message = _CONTROL_CHARS.sub("", (message or "").strip())

    if not is_valid_email(email):
        raise ContactRejected("invalid e-mail address")
    if not 3 <= len(subject) <= 160:
        raise ContactRejected("invalid subject")
    if not 10 <= len(message) <= 4000:
        raise ContactRejected("invalid message")
    return email, subject, message


def store_submission(
    db: Session, *, email: str, subject: str, message: str, ip: str = ""
) -> ContactMessage:
    """Persist a validated contact message."""
    from .audit import hash_ip

    record = ContactMessage(
        email_ciphertext=encrypt_bytes(email.encode("utf-8"), aad=b"contact-email"),
        email_hash=hash_value(email),
        subject=subject,
        body=message,
        ip_hash=hash_ip(ip),
        status="new",
        created_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
