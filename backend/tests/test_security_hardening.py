"""Regression tests for Phase 1 security hardening: production validation, rate limiting, and RBAC."""

from __future__ import annotations

import pytest
from fastapi import status
from pydantic import SecretStr

from backend.app.core.config import Settings
from backend.app.core.ratelimit import login_limiter
from backend.app.core.security import redact_stream_url, validate_stream_url


def test_production_config_rejects_insecure_secrets():
    """Verify that production mode fails safely when default or short secrets are used."""
    # Insecure dev secret key in production
    with pytest.raises(ValueError, match="SURVEILLANCE_SECRET_KEY"):
        Settings(
            app_env="production",
            secret_key=SecretStr("insecure-dev-secret-key-at-least-32-chars-long"),
            biometric_encryption_key=SecretStr("super-strong-valid-secret-key-for-bio-32!"),
            cors_origins=["https://secure.example.com"],
            trusted_hosts=["secure.example.com"],
        )

    # Insecure dev biometric key in production
    with pytest.raises(ValueError, match="SURVEILLANCE_BIOMETRIC_ENCRYPTION_KEY"):
        Settings(
            app_env="production",
            secret_key=SecretStr("super-strong-valid-secret-key-for-auth-32!"),
            biometric_encryption_key=SecretStr("insecure-biometric-key-at-least-32-chars-long"),
            cors_origins=["https://secure.example.com"],
            trusted_hosts=["secure.example.com"],
        )

    # Wildcard CORS in production
    with pytest.raises(ValueError, match="Wildcard CORS origins"):
        Settings(
            app_env="production",
            secret_key=SecretStr("super-strong-valid-secret-key-for-auth-32!"),
            biometric_encryption_key=SecretStr("super-strong-valid-secret-key-for-bio-32!"),
            cors_origins=["*"],
            trusted_hosts=["secure.example.com"],
        )

    # Valid production settings pass
    valid_prod = Settings(
        app_env="production",
        secret_key=SecretStr("super-strong-valid-secret-key-for-auth-32!"),
        biometric_encryption_key=SecretStr("super-strong-valid-secret-key-for-bio-32!"),
        cors_origins=["https://secure.example.com"],
        trusted_hosts=["secure.example.com"],
    )
    assert valid_prod.app_env == "production"


def test_login_rate_limiting(client):
    """Verify that rapid repeated login attempts trigger HTTP 429 Too Many Requests."""
    login_limiter.reset()

    # Send 5 failed login attempts
    for _ in range(5):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "ratelimit_target@surveillance.local", "password": "WrongPassword99!"},
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # The 6th attempt must be throttled with 429 Too Many Requests
    throttled = client.post(
        "/api/v1/auth/login",
        json={"email": "ratelimit_target@surveillance.local", "password": "WrongPassword99!"},
    )
    assert throttled.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Retry-After" in throttled.headers
    assert "Too many failed login attempts" in throttled.json()["detail"]

    # Clean up for following tests
    login_limiter.reset()


def test_viewer_forbidden_from_audit_logs(client, viewer_headers, admin_headers):
    """Verify that only owner/admin roles can access security audit logs."""
    # Viewer must be rejected with 403 Forbidden
    viewer_resp = client.get("/api/v1/audit-logs", headers=viewer_headers)
    assert viewer_resp.status_code == status.HTTP_403_FORBIDDEN
    assert "owner or admin" in viewer_resp.json()["detail"].lower()

    # Admin must succeed
    admin_resp = client.get("/api/v1/audit-logs", headers=admin_headers)
    assert admin_resp.status_code == status.HTTP_200_OK


def test_viewer_forbidden_from_reports(client, viewer_headers, admin_headers):
    """Verify that viewer role cannot access analytics summary or event CSV export."""
    # Summary
    resp_sum = client.get("/api/v1/reports/summary", headers=viewer_headers)
    assert resp_sum.status_code == status.HTTP_403_FORBIDDEN

    # Export CSV
    resp_exp = client.get("/api/v1/reports/export", headers=viewer_headers)
    assert resp_exp.status_code == status.HTTP_403_FORBIDDEN

    # Admin access succeeds
    resp_admin_sum = client.get("/api/v1/reports/summary", headers=admin_headers)
    assert resp_admin_sum.status_code == status.HTTP_200_OK

    resp_admin_exp = client.get("/api/v1/reports/export", headers=admin_headers)
    assert resp_admin_exp.status_code == status.HTTP_200_OK
    assert "text/csv" in resp_admin_exp.headers.get("content-type", "")


def test_snapshot_path_traversal_blocked(client, admin_headers):
    """Verify that path traversal attempts on the snapshot retrieval endpoint return 404."""
    resp1 = client.get("/api/v1/stream/snapshot/../../etc/passwd", headers=admin_headers)
    assert resp1.status_code == status.HTTP_404_NOT_FOUND

    resp2 = client.get("/api/v1/stream/snapshot/..%2f..%2fmain.py", headers=admin_headers)
    assert resp2.status_code == status.HTTP_404_NOT_FOUND


def test_stream_url_ssrf_and_redaction():
    """Verify enhanced SSRF protection for IPv6/metadata addresses and RTSP credential redaction."""
    # IPv6 link-local metadata blocked
    ok, msg = validate_stream_url("http://fd00:ec2::254/latest/meta-data/", source_type="rtsp")
    assert ok is False
    assert "ssrf" in msg.lower() or "cloud metadata" in msg.lower()

    # ECS metadata address blocked
    ok, msg = validate_stream_url("http://169.254.170.2/v2/metadata", source_type="rtsp")
    assert ok is False

    # Decimal integer IP format for 169.254.169.254 blocked
    ok, msg = validate_stream_url("http://2852039166/cam", source_type="ip_camera")
    assert ok is False
    assert "ssrf" in msg.lower() or "cloud metadata" in msg.lower()

    # Hex IP format for 169.254.169.254 blocked
    ok, msg = validate_stream_url("http://0xa9fea9fe/cam", source_type="ip_camera")
    assert ok is False
    assert "ssrf" in msg.lower() or "cloud metadata" in msg.lower()

    # Credential redaction
    redacted = redact_stream_url("rtsp://admin:secretPass123@192.168.1.100:554/stream1")
    assert "secretPass123" not in redacted
    assert "rtsp://admin:***@192.168.1.100:554/stream1" == redacted

    # Non-credential URL remains untouched
    clean_url = "rtsp://192.168.1.100:554/stream1"
    assert redact_stream_url(clean_url) == clean_url
