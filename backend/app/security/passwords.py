"""Argon2id password hashing (RFC 9106-recommended parameters)."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# OWASP 2024 guidance: Argon2id, m=19MiB t=2 p=1 minimum; we exceed it.
_hasher = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=2)


class PasswordError(Exception):
    pass


def hash_password(password: str) -> str:
    if not password or len(password) < 8:
        raise PasswordError("password must be at least 8 characters")
    return _hasher.hash(password)


def verify_password(hash_value: str, password: str) -> bool:
    """Return True on match; False on mismatch or malformed hash (never raises)."""
    try:
        return _hasher.verify(hash_value, password)
    except (VerificationError, InvalidHashError, ValueError):
        return False


def needs_rehash(hash_value: str) -> bool:
    """True when the stored hash uses weaker parameters than configured."""
    try:
        return _hasher.check_needs_rehash(hash_value)
    except (InvalidHashError, ValueError):
        return True


def password_strength_error(password: str) -> str | None:
    """Human-readable weakness description, or None when acceptable."""
    checks = [
        (len(password) >= 12, "use at least 12 characters"),
        (len(password) < 200, "password too long"),
        (any(c.islower() for c in password) or len(password) >= 24,
         "mix character cases (or use a long passphrase)"),
        (any(c.isdigit() for c in password) or len(password) >= 24,
         "include a digit (or use a long passphrase)"),
    ]
    for ok, message in checks:
        if not ok:
            return message
    return None
