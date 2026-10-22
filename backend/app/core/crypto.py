"""AES-256-GCM cryptographic primitives for biometric templates and credentials."""

from __future__ import annotations

import hashlib
import os
from typing import Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import get_settings


class CryptoError(Exception):
    pass


def _derive_key(secret: Optional[str] = None) -> bytes:
    if secret is None:
        cfg = get_settings().biometric_encryption_key
        secret = cfg.get_secret_value() if cfg else "surveillance-default-secret-key-32b"
    return hashlib.sha256(secret.encode("utf-8")).digest()


def encrypt_bytes(plaintext: bytes, aad: bytes = b"", secret: Optional[str] = None) -> bytes:
    """Encrypt plaintext using AES-256-GCM, returning nonce (12B) + ciphertext + tag."""
    key = _derive_key(secret)
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, aad or None)
    return nonce + ciphertext


def decrypt_bytes(payload: bytes, aad: bytes = b"", secret: Optional[str] = None) -> bytes:
    """Decrypt payload using AES-256-GCM."""
    if len(payload) <= 12:
        raise CryptoError("Encrypted payload too short")
    key = _derive_key(secret)
    nonce = payload[:12]
    ciphertext = payload[12:]
    aesgcm = AESGCM(key)
    try:
        return aesgcm.decrypt(nonce, ciphertext, aad or None)
    except InvalidTag as err:
        raise CryptoError("Authentication tag verification failed; invalid key or corrupt data") from err


def encrypt_string(text: str, aad: bytes = b"") -> bytes:
    return encrypt_bytes(text.encode("utf-8"), aad=aad)


def decrypt_string(payload: bytes, aad: bytes = b"") -> str:
    return decrypt_bytes(payload, aad=aad).decode("utf-8")
