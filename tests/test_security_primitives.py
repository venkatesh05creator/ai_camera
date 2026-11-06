"""Security primitives: Argon2id, AES-256-GCM, SSRF validator, TOTP."""

from __future__ import annotations

import base64
import hashlib
import socket

import pytest

from backend.app.security import crypto, passwords, ssrf, totp


# ---------------------------------------------------------------- passwords
def test_argon2id_roundtrip():
    h = passwords.hash_password("correct horse battery staple")
    assert h.startswith("$argon2id$")
    assert passwords.verify_password(h, "correct horse battery staple")
    assert not passwords.verify_password(h, "wrong password")
    # malformed / tampered hash never raises, just False
    assert not passwords.verify_password("$argon2id$garbage", "x" * 20)
    assert passwords.needs_rehash("$argon2id$garbage")


def test_argon2id_rejects_short_password():
    with pytest.raises(passwords.PasswordError):
        passwords.hash_password("short")


def test_password_strength_messages():
    assert passwords.password_strength_error("hunter2") is not None
    assert passwords.password_strength_error("correct horse battery staple") is None


# ------------------------------------------------------------------- crypto
def test_aes_gcm_roundtrip_and_tamper():
    key = crypto.derive_key("k" * 40)
    blob = crypto.encrypt(key, b"secret face data")
    assert blob != b"secret face data"
    assert crypto.decrypt(key, blob) == b"secret face data"

    # flipping one bit anywhere must fail authentication
    for pos in (2, 20):
        tampered = bytearray(blob)
        tampered[pos] ^= 0x01
        with pytest.raises(crypto.CryptoError):
            crypto.decrypt(key, bytes(tampered))

    # wrong key fails
    with pytest.raises(crypto.CryptoError):
        crypto.decrypt(crypto.derive_key("other"), blob)


def test_aes_gcm_text_helpers():
    key = crypto.derive_key("passphrase")
    token = crypto.encrypt_text(key, "session-secret-123")
    assert "session-secret-123" not in token
    assert crypto.decrypt_text(key, token) == "session-secret-123"
    with pytest.raises(crypto.CryptoError):
        crypto.decrypt_text(key, "not-a-valid-token!!!")


def test_derive_key_forms():
    hex_secret = hashlib.sha256(b"x").hexdigest()  # 64 hex chars -> 32 bytes
    assert crypto.derive_key(hex_secret) == hashlib.sha256(b"x").digest()
    b64_secret = base64.b64encode(bytes(range(32))).decode()
    assert crypto.derive_key(b64_secret) == bytes(range(32))
    assert len(crypto.derive_key("some pass phrase")) == 32
    with pytest.raises(crypto.CryptoError):
        crypto.encrypt(b"short", b"data")


# --------------------------------------------------------------- ssrf
def _fake_resolver(records):
    def resolver(host, port, type=socket.SOCK_STREAM, timeout=10.0):  # noqa: A002
        if host not in records:
            raise socket.gaierror(8, "nodename nor servname provided")
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, port))
                for ip in records[host]]
    return resolver


def test_ssrf_blocks_private_targets(monkeypatch):
    monkeypatch.setattr(ssrf, "_resolver", _fake_resolver({
        "internal.corp": ["192.168.1.10"],
        "metadata.aws": ["169.254.169.254"],
        "loopback.io": ["127.0.0.1"],
        "v6private.io": ["fd12:3456::1"],
        "mapped.io": ["::ffff:10.0.0.5"],
    }))
    for url in ("http://internal.corp/cam", "http://metadata.aws/latest",
                "http://loopback.io/", "http://v6private.io/",
                "http://mapped.io/", "ftp://files.example.com/x",
                "http://user:pw@evil.io/"):
        with pytest.raises(ssrf.SSRFError):
            ssrf.validate_url(url)


def test_ssrf_allows_global_and_private_mode(monkeypatch):
    monkeypatch.setattr(ssrf, "_resolver", _fake_resolver({
        "cam.example.com": ["93.184.216.34"],
        "localcam.local": ["192.168.1.50"],
    }))
    ok = ssrf.validate_url("https://cam.example.com/mjpeg")
    assert ok.ip == "93.184.216.34"
    assert ok.port == 443
    # explicit escape hatch allows private hosts (owner's own LAN camera)
    ok2 = ssrf.validate_url("http://localcam.local:8080/stream",
                            allow_private=True)
    assert ok2.ip == "192.168.1.50"
    assert ok2.port == 8080


def test_ssrf_requires_resolvable_host(monkeypatch):
    monkeypatch.setattr(ssrf, "_resolver", _fake_resolver({}))
    with pytest.raises(ssrf.SSRFError):
        ssrf.validate_url("http://nonexistent.invalid/stream")


# --------------------------------------------------------------------- totp
def test_totp_enroll_verify_roundtrip():
    secret = totp.new_secret()
    uri = totp.provisioning_uri(secret, "owner@localhost")
    assert "issuer=Aegis" in uri or "Aegis%20AI" in uri
    code = totp.current_code(secret)
    assert totp.verify_code(secret, code)
    assert not totp.verify_code(secret, "000000" if code != "000000" else "111111")
    # garbage / wrong length rejected before touching the TOTP algorithm
    assert not totp.verify_code(secret, "12345")
    assert not totp.verify_code(secret, "abcdef")
    assert not totp.verify_code(secret, "")
