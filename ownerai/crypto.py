"""Symmetric encryption helpers (AES-GCM) and data-redaction utilities.

Biometric templates and contact e-mail addresses are stored encrypted at rest.
The key never leaves the server: it is supplied through the
``OWNERAI_BIOMETRIC_ENCRYPTION_KEY`` environment variable.
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
import secrets
from typing import Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .settings import get_settings

# A key of 32 bytes (AES-256) derived from the configured secret.
_KEY_LENGTH = 32


class EncryptionError(RuntimeError):
    """Raised when a payload cannot be encrypted or decrypted."""


def _derive_key(secret: str) -> bytes:
    """Derive a fixed-length key from an arbitrary secret string."""
    return hashlib.sha256(secret.encode("utf-8")).digest()


def _load_key(secret: Optional[str] = None) -> bytes:
    if secret is None:
        configured = get_settings().biometric_encryption_key
        if configured is None or not configured.get_secret_value():
            raise EncryptionError(
                "OWNERAI_BIOMETRIC_ENCRYPTION_KEY is not configured; "
                "set it before storing encrypted templates."
            )
        secret = configured.get_secret_value()
    if not secret:
        raise EncryptionError("an encryption key is required")
    return _derive_key(secret)


def encrypt_bytes(plaintext: bytes, *, aad: bytes = b"", secret: Optional[str] = None) -> bytes:
    """Encrypt ``plaintext`` with AES-GCM, returning ``nonce || ciphertext``."""
    key = _load_key(secret)
    nonce = os.urandom(12)
    cipher = AESGCM(key)
    return nonce + cipher.encrypt(nonce, plaintext, aad or None)


def decrypt_bytes(payload: bytes, *, aad: bytes = b"", secret: Optional[str] = None) -> bytes:
    """Decrypt a payload produced by :func:`encrypt_bytes`."""
    if not payload or len(payload) <= 12:
        raise EncryptionError("malformed encrypted payload")
    key = _load_key(secret)
    nonce, ciphertext = payload[:12], payload[12:]
    cipher = AESGCM(key)
    try:
        return cipher.decrypt(nonce, ciphertext, aad or None)
    except InvalidTag as exc:  # pragma: no cover - triggered by tampering
        raise EncryptionError("could not decrypt payload") from exc


def encrypt_text(text: str, *, aad: bytes = b"", secret: Optional[str] = None) -> bytes:
    return encrypt_bytes(text.encode("utf-8"), aad=aad, secret=secret)


def decrypt_text(payload: bytes, *, aad: bytes = b"", secret: Optional[str] = None) -> str:
    return decrypt_bytes(payload, aad=aad, secret=secret).decode("utf-8")


def generate_data_key() -> str:
    """Return a fresh base64 encoded 32-byte key (for operators)."""
    return base64.b64encode(os.urandom(_KEY_LENGTH)).decode("ascii")


def hash_value(value: str, *, pepper: Optional[str] = None) -> str:
    """Salted, peppered SHA-256 used for non-reversible indexes (e.g. e-mails)."""
    salt = get_settings().secret_key.get_secret_value() if pepper is None else pepper
    return hashlib.sha256(f"{salt}:{value}".encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_LONG_DIGITS_RE = re.compile(r"\b\d{9,}\b")


def redact_pii(text: str) -> str:
    """Remove e-mail addresses, IPs and long digit sequences from free text.

    Used before sending context to a third-party AI provider.
    """
    if not text:
        return ""
    redacted = _EMAIL_RE.sub("[redacted-email]", text)
    redacted = _IPV4_RE.sub("[redacted-ip]", redacted)
    redacted = _LONG_DIGITS_RE.sub("[redacted-number]", redacted)
    return redacted


def mask_email(email: str) -> str:
    """Return a masked representation of an e-mail address."""
    if "@" not in email:
        return "***"
    local, _, domain = email.partition("@")
    keep = local[:1] if len(local) > 1 else ""
    return f"{keep}***@{domain}"


def constant_time_equals(left: str, right: str) -> bool:
    """Timing-safe string comparison."""
    import hmac

    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def random_token(nbytes: int = 32) -> str:
    """Cryptographically secure, URL-safe token."""
    return secrets.token_urlsafe(nbytes)
