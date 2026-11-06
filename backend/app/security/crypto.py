"""AES-256-GCM authenticated encryption helpers (Phase 3+ storage crypto).

Blob format: ``nonce(12B) || AESGCM(key, nonce, plaintext, aad)``.
Keys are exactly 32 bytes; :func:`derive_key` converts a user-supplied secret
string (hex / base64 / passphrase) into the required 32-byte key.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_BYTES = 12
KEY_BYTES = 32


class CryptoError(Exception):
    """Raised when key material or ciphertext is invalid."""


def derive_key(secret: str) -> bytes:
    """Convert key material into exactly 32 bytes.

    - 64 hex chars -> decoded as hex
    - 44/43-char base64 (or 32 raw bytes decoded) -> decoded
    - anything else -> SHA-256 of the UTF-8 string (deterministic KDF)
    """
    secret = secret.strip()
    if len(secret) >= 64 and all(c in "0123456789abcdefABCDEF" for c in secret[:64]):
        try:
            decoded = binascii.unhexlify(secret[:64])
            if len(decoded) == KEY_BYTES:
                return decoded
        except binascii.Error:
            pass
    try:
        decoded = base64.b64decode(secret + "=" * (-len(secret) % 4), validate=True)
        if len(decoded) == KEY_BYTES:
            return decoded
    except (binascii.Error, ValueError):
        pass
    return hashlib.sha256(secret.encode("utf-8")).digest()


def encrypt(key32: bytes, plaintext: bytes, *, aad: bytes | None = None) -> bytes:
    """Encrypt and authenticate; returns nonce || ciphertext."""
    if len(key32) != KEY_BYTES:
        raise CryptoError("key must be exactly 32 bytes")
    nonce = os.urandom(NONCE_BYTES)
    return nonce + AESGCM(key32).encrypt(nonce, plaintext, aad)


def decrypt(key32: bytes, blob: bytes, *, aad: bytes | None = None) -> bytes:
    """Decrypt a nonce||ciphertext blob; raises CryptoError on tampering."""
    if len(key32) != KEY_BYTES:
        raise CryptoError("key must be exactly 32 bytes")
    if len(blob) <= NONCE_BYTES:
        raise CryptoError("ciphertext too short")
    nonce, ct = blob[:NONCE_BYTES], blob[NONCE_BYTES:]
    try:
        return AESGCM(key32).decrypt(nonce, ct, aad)
    except InvalidTag as exc:
        raise CryptoError("decryption failed: ciphertext tampered or wrong key") from exc


def encrypt_text(key32: bytes, text: str, *, aad: bytes | None = None) -> str:
    """Encrypt a string, return url-safe base64 (no trailing '=' padding)."""
    raw = encrypt(key32, text.encode("utf-8"), aad=aad)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def decrypt_text(key32: bytes, token: str, *, aad: bytes | None = None) -> str:
    """Inverse of :func:`encrypt_text`; raises CryptoError on tampering."""
    padded = token + "=" * (-len(token) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded)
    except (binascii.Error, ValueError) as exc:
        raise CryptoError("invalid token encoding") from exc
    return decrypt(key32, raw, aad=aad).decode("utf-8")
