"""RFC 6238 (TOTP) and RFC 4226 (HOTP) implementations.

Used for optional multi-factor authentication.  Only standard library
primitives are used; no custom cryptography is implemented.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import struct
import time
from typing import List

from .crypto import constant_time_equals

DIGITS = 6
DEFAULT_STEP_SECONDS = 30


def generate_secret(nbytes: int = 20) -> str:
    """Return a base32 encoded shared secret."""
    import os

    return base64.b32encode(os.urandom(nbytes)).decode("ascii").rstrip("=")


def _decode_secret(secret: str) -> bytes:
    padding = "=" * ((8 - len(secret) % 8) % 8)
    return base64.b32decode(secret.upper() + padding, casefold=True)


def hotp(secret: str, counter: int, digits: int = DIGITS) -> str:
    """Compute an HOTP value (RFC 4226)."""
    key = _decode_secret(secret)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10**digits)).zfill(digits)


def totp(
    secret: str,
    *,
    step_seconds: int = DEFAULT_STEP_SECONDS,
    digits: int = DIGITS,
    timestamp: float | None = None,
) -> str:
    """Compute the TOTP value for the current time step."""
    now = time.time() if timestamp is None else timestamp
    counter = int(now // step_seconds)
    return hotp(secret, counter, digits=digits)


def verify_totp(
    secret: str,
    code: str,
    *,
    step_seconds: int = DEFAULT_STEP_SECONDS,
    window: int = 1,
    digits: int = DIGITS,
    timestamp: float | None = None,
) -> bool:
    """Verify a TOTP code allowing ``window`` steps of clock drift."""
    if not code or not code.isdigit():
        return False
    now = time.time() if timestamp is None else timestamp
    counter = int(now // step_seconds)
    for offset in range(-window, window + 1):
        candidate = hotp(secret, counter + offset, digits=digits)
        if constant_time_equals(candidate, code.zfill(digits)):
            return True
    return False


def provisioning_uri(secret: str, account: str, issuer: str) -> str:
    """Build the ``otpauth://`` URI consumed by authenticator apps."""
    from urllib.parse import quote

    label = quote(f"{issuer}:{account}", safe="")
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer, safe='')}&algorithm=SHA1&digits={DIGITS}&period={DEFAULT_STEP_SECONDS}"


def backup_codes(count: int = 8) -> List[str]:
    """Generate single-use backup codes."""
    from .crypto import random_token

    return [random_token(6)[:10] for _ in range(count)]
