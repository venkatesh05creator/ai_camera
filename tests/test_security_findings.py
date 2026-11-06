"""Regression tests for security findings (docs/security/findings.md).

These tests lock in the security behaviour described in findings.md so that
a future change cannot silently weaken it.
"""

from __future__ import annotations

import os
import shutil
import subprocess

from ownerai.crypto import EncryptionError, decrypt_bytes, encrypt_bytes
from ownerai.middleware import client_ip
from ownerai.settings import get_settings

_GIT = shutil.which("git") or "git"


# ---------------------------------------------------------------------------
# F-004: AES-GCM round-trip + tamper detection
# ---------------------------------------------------------------------------
def test_encrypt_decrypt_round_trip():
    plaintext = b"biometric template payload"
    token = encrypt_bytes(plaintext)
    assert decrypt_bytes(token) == plaintext


def test_encrypt_decrypt_with_aad():
    plaintext = b"contact address"
    aad = b"device-42"
    token = encrypt_bytes(plaintext, aad=aad)
    assert decrypt_bytes(token, aad=aad) == plaintext


def test_tampered_ciphertext_raises():
    token = bytearray(encrypt_bytes(b"secret data"))
    # Flip a bit in the ciphertext portion (after the 12-byte nonce).
    token[15] ^= 0xFF
    try:
        decrypt_bytes(bytes(token))
    except EncryptionError:
        pass
    else:
        raise AssertionError("tampered ciphertext was accepted")


def test_truncated_payload_raises():
    try:
        decrypt_bytes(b"short")
    except EncryptionError:
        pass
    else:
        raise AssertionError("truncated payload was accepted")


# ---------------------------------------------------------------------------
# F-002: client_ip falls back to direct connection when proxy headers off
# ---------------------------------------------------------------------------
def test_client_ip_ignores_xff_when_proxy_headers_off(monkeypatch):
    """With trust_proxy_headers=false, X-Forwarded-For must not be trusted."""
    settings = get_settings()
    assert settings.trust_proxy_headers is False  # dev default

    class FakeRequest:
        client = type("C", (), {"host": "10.0.0.5"})()

    # client_ip reads settings directly; with the flag off it uses client.host.
    assert client_ip(FakeRequest()) == "10.0.0.5"


# ---------------------------------------------------------------------------
# F-003 / F-008: nothing sensitive tracked in git
# ---------------------------------------------------------------------------
def test_no_secrets_or_embeddings_tracked():
    tracked = subprocess.run(  # noqa: S603 - trusted read-only git command, no user input
        [_GIT, "ls-files"],
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    forbidden = [".env", "datastore/", "data/Faces/", "secrets/"]
    for item in forbidden:
        matches = [t for t in tracked if t == item or t.startswith(item + "/")]
        assert not matches, f"tracked sensitive path: {matches}"


def test_env_example_tracked_but_env_not():
    tracked = subprocess.run(  # noqa: S603 - trusted read-only git command, no user input
        [_GIT, "ls-files"],
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    assert ".env.example" in tracked
    assert ".env" not in tracked


def test_no_web_dist_tracked():
    tracked = subprocess.run(  # noqa: S603 - trusted read-only git command, no user input
        [_GIT, "ls-files"],
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    assert not any(t.startswith("web/dist/") for t in tracked)
    assert not any(t.startswith("web/node_modules/") for t in tracked)


# ---------------------------------------------------------------------------
# F-006: security workflow exists
# ---------------------------------------------------------------------------
def test_security_workflow_exists():
    assert os.path.exists(".github/workflows/security.yml")


# ---------------------------------------------------------------------------
# F-007: ownerai/main:app is the live entry point
# ---------------------------------------------------------------------------
def test_live_entry_point_is_ownerai():
    # app.py re-exports ownerai.main:app
    import ownerai.main  # noqa: F401
    from ownerai.main import create_app
    app = create_app()
    assert app is not None
