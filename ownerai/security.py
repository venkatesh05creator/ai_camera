"""Authentication primitives: password hashing, session tokens and CSRF."""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from .crypto import constant_time_equals, random_token
from .settings import Settings, get_settings

logger = logging.getLogger(__name__)

# OWASP-aligned Argon2id parameters (64 MiB, 3 iterations, 4 lanes).
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Hash a password with Argon2id."""
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    """Verify a password against a stored Argon2id hash."""
    if not stored_hash or not password:
        return False
    try:
        _hasher.verify(stored_hash, password)
        return True
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    except Exception:  # pragma: no cover - defensive, never leak internals
        logger.warning("password verification failed unexpectedly", exc_info=False)
        return False


def password_needs_rehash(stored_hash: str) -> bool:
    """Return ``True`` when a hash uses outdated parameters."""
    try:
        return _hasher.check_needs_rehash(stored_hash)
    except InvalidHashError:  # pragma: no cover - corrupted hash
        return True


def dummy_verify() -> None:
    """Burn roughly the same amount of CPU as a real verification.

    Used to keep the timing of "unknown user" and "wrong password" similar,
    which limits account enumeration through timing side channels.
    """
    try:
        _hasher.verify(
            "$argon2id$v=19$m=65536,t=3,p=4$Y2FuYXJ5$Zm9vYmFyYmF6cXV1eGNvcmdlbm9wZXJhdHVyZQ",
            "not-a-real-password",
        )
    except Exception:
        return None


def validate_password_strength(password: str, settings: Optional[Settings] = None) -> list[str]:
    """Return a list of human readable problems with the supplied password."""
    settings = settings or get_settings()
    problems: list[str] = []
    if len(password) < settings.password_min_length:
        problems.append(f"must be at least {settings.password_min_length} characters long")
    if len(password) > settings.password_max_length:
        problems.append(f"must be at most {settings.password_max_length} characters long")
    if password.lower() == password or password.upper() == password:
        problems.append("must mix upper and lower case characters")
    if not any(ch.isdigit() for ch in password):
        problems.append("must contain a digit")
    if not any(not ch.isalnum() for ch in password):
        problems.append("must contain a symbol")
    if password.lower() in {"password", "12345678", "qwertyuiop", "letmein123"}:
        problems.append("is too common")
    return problems


def normalise_email(email: str) -> str:
    """Normalise an e-mail address for storage and lookups."""
    return (email or "").strip().lower()


def is_valid_email(email: str) -> bool:
    """Validate the shape of an e-mail address (no delivery is attempted)."""
    return bool(email) and len(email) <= 320 and bool(EMAIL_RE.match(email))


# ---------------------------------------------------------------------------
# Session tokens
# ---------------------------------------------------------------------------
def new_session_token() -> str:
    """Create a 256-bit, URL-safe session identifier."""
    return random_token(32)


def hash_token(token: str) -> str:
    """Hash a bearer token for storage (SHA-256)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_csrf_token() -> str:
    """Create a CSRF token."""
    return random_token(32)


def sign_csrf_token(nonce: str, settings: Optional[Settings] = None) -> str:
    """Sign an anonymous CSRF nonce with the application secret."""
    settings = settings or get_settings()
    secret = settings.secret_key.get_secret_value()
    signature = hashlib.sha256(f"csrf:{nonce}:{secret}".encode("utf-8")).hexdigest()
    return f"{nonce}.{signature}"


def verify_signed_csrf_token(value: str, settings: Optional[Settings] = None) -> bool:
    """Validate a signed anonymous CSRF token."""
    if not value or "." not in value:
        return False
    nonce, _, signature = value.partition(".")
    expected = sign_csrf_token(nonce, settings).partition(".")[2]
    return constant_time_equals(signature, expected)


# ---------------------------------------------------------------------------
# Timestamps
# ---------------------------------------------------------------------------
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    """Normalise a datetime to timezone-aware UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def is_expired(value: datetime | None) -> bool:
    """Return ``True`` when the timestamp is in the past."""
    if value is None:
        return True
    normalised = as_utc(value)
    if normalised is None:  # pragma: no cover - defensive
        return True
    return normalised <= utcnow()


@dataclass(frozen=True)
class SessionLifetime:
    """Computed expiry information for a new session."""

    expires_at: datetime
    absolute_expires_at: datetime


def session_lifetime(settings: Optional[Settings] = None) -> SessionLifetime:
    """Calculate idle and absolute expiry for a freshly created session."""
    settings = settings or get_settings()
    now = utcnow()
    return SessionLifetime(
        expires_at=now + timedelta(minutes=settings.session_idle_minutes),
        absolute_expires_at=now + timedelta(minutes=settings.session_absolute_minutes),
    )
