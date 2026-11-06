"""TOTP two-factor enrollment and verification (RFC 6238, via pyotp)."""

from __future__ import annotations

import pyotp

ISSUER_NAME = "Aegis AI"


def new_secret() -> str:
    """Fresh Base32 secret (160 bits of entropy)."""
    return pyotp.random_base32()


def provisioning_uri(secret: str, account_email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=account_email, issuer_name=ISSUER_NAME)


def current_code(secret: str) -> str:
    return pyotp.totp.TOTP(secret).now()


def verify_code(secret: str, code: str, *, valid_window: int = 1) -> bool:
    """Verify a 6-digit code (±1 step of clock drift). Rejects non-digits."""
    code = code.strip().replace(" ", "")
    if not code.isdigit() or len(code) != 6:
        return False
    return pyotp.totp.TOTP(secret).verify(code, valid_window=valid_window)
