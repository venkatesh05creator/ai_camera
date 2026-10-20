"""API hardening tests: validation, injection, headers, limits and disclosure."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from ownerai.db import get_engine
from ownerai.models import Device, User

from .conftest import auth_headers

SECRET_MARKER = "test-secret-key-that-is-long-enough-for-tests-0123456789"


def test_security_headers_are_present(client):
    response = client.get("/")
    headers = response.headers
    assert "Content-Security-Policy" in headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert "Referrer-Policy" in headers
    assert "Permissions-Policy" in headers
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert "camera=(self)" in headers["Permissions-Policy"]


def test_authenticated_pages_are_not_cached(client, owner):
    response = owner.get("/dashboard")
    assert "no-store" in response.headers.get("Cache-Control", "")


def test_content_security_policy_forbids_inline_script(client):
    response = client.get("/")
    csp = response.headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp
    assert "unsafe-inline" not in csp
    assert "unsafe-eval" not in csp


def test_pages_do_not_contain_inline_scripts_or_handlers(client):
    for path in ["/", "/login", "/register", "/docs"]:
        body = client.get(path).text
        assert "<script>" not in body
        assert "javascript:" not in body
        assert "onclick=" not in body
        assert "onerror=" not in body


def test_sql_injection_payload_is_treated_as_data(client, owner):
    payload = "'; DROP TABLE devices; --"
    response = owner.post(
        "/api/devices",
        json={"name": payload, "device_type": "webcam"},
        headers=auth_headers(owner),
    )
    assert response.status_code == 201
    with Session(get_engine()) as session:
        device = session.query(Device).filter(Device.name == payload).one()
        assert device.name == payload
        assert session.query(Device).count() == 1


def test_search_with_sql_injection_does_not_change_the_query(client, owner):
    response = owner.get("/api/search?q=%27%3B+DROP+TABLE+users%3B--")
    assert response.status_code == 200
    with Session(get_engine()) as session:
        assert session.query(User).count() >= 1


def test_xss_payload_is_escaped_in_the_rendered_page(client, owner):
    payload = "<script>alert('xss')</script>"
    response = owner.post(
        "/api/devices",
        json={"name": payload, "device_type": "webcam"},
        headers=auth_headers(owner),
    )
    assert response.status_code == 201
    body = client.get("/dashboard").text
    assert payload not in body


def test_unknown_fields_are_rejected(client, owner):
    response = owner.post(
        "/api/devices",
        json={"name": "cam", "device_type": "webcam", "owner_id": 999},
        headers=auth_headers(owner),
    )
    assert response.status_code == 422


def test_invalid_enum_values_are_rejected(client, owner):
    response = owner.post(
        "/api/devices",
        json={"name": "cam", "device_type": "satellite"},
        headers=auth_headers(owner),
    )
    assert response.status_code == 422


def test_oversized_body_is_rejected(client, owner):
    payload = {"name": "x" * 200, "device_type": "webcam"}
    body = json.dumps(payload)
    response = owner.post(
        "/api/devices",
        content=body,
        headers={**auth_headers(owner), "Content-Type": "application/json"},
    )
    assert response.status_code == 422


def test_huge_request_body_is_rejected_before_parsing(client, owner):
    huge = "A" * (9 * 1024 * 1024)
    response = owner.post(
        "/api/devices",
        content=json.dumps({"name": huge, "device_type": "webcam"}),
        headers={**auth_headers(owner), "Content-Type": "application/json"},
    )
    assert response.status_code == 413


def test_errors_do_not_leak_internals(client, owner):
    response = owner.post(
        "/api/devices",
        json={"name": "cam", "device_type": "webcam", "stream_url": "file:///etc/passwd"},
        headers=auth_headers(owner),
    )
    assert response.status_code in (400, 422)
    body = response.text
    assert "Traceback" not in body
    assert "ownerai\\" not in body


def test_secrets_are_never_returned_by_the_api(client, owner):
    for path in ["/api/auth/me", "/api/devices", "/api/identities", "/api/admin/stats"]:
        response = owner.get(path)
        assert SECRET_MARKER not in response.text


def test_secrets_are_not_embedded_in_the_static_assets(client):
    for asset in ["/static/js/app.js", "/static/js/dashboard.js", "/static/js/admin.js", "/static/css/app.css"]:
        response = client.get(asset)
        assert response.status_code == 200
        assert SECRET_MARKER not in response.text
        assert "ownerai_secret_key" not in response.text.lower()


def test_debug_endpoints_are_not_exposed(client):
    """The interactive API documentation must not be published."""
    from ownerai.main import create_app
    from ownerai.settings import Settings

    production = Settings(
        app_env="production",
        secret_key="a-very-long-production-secret-key-0123456789abcdef",
        https_only=True,
        hsts_enabled=True,
        trusted_hosts=["example.test"],
        database_url="sqlite:///:memory:",
    )
    app = create_app(production)
    from fastapi.testclient import TestClient

    with TestClient(app, base_url="http://example.test") as production_client:
        assert production_client.get("/api/docs").status_code == 404
        assert production_client.get("/api/openapi.json").status_code == 404


def test_api_rate_limit_returns_429(client, owner):
    """Repeated search requests are bounded."""
    response = None
    for _ in range(31):
        response = owner.get("/api/search?q=camera")
    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_contact_form_is_rate_limited_and_ignores_the_honeypot(client):
    for _ in range(3):
        client.post(
            "/api/contact",
            json={
                "email": "someone@example.test",
                "subject": "Hello there",
                "message": "This is a message with enough length.",
                "website": "",
            },
            headers=auth_headers(client),
        )
    blocked = client.post(
        "/api/contact",
        json={
            "email": "someone@example.test",
            "subject": "Hello there",
            "message": "This is a message with enough length.",
            "website": "",
        },
        headers=auth_headers(client),
    )
    assert blocked.status_code == 429


def test_contact_form_rejects_invalid_input(client):
    response = client.post(
        "/api/contact",
        json={"email": "not-an-email", "subject": "x", "message": "short"},
        headers=auth_headers(client),
    )
    assert response.status_code == 422


def test_private_files_are_not_served(client):
    for path in [
        "/.env",
        "/.git/config",
        "/requirements.txt",
        "/datastore/datastore_512_Dim.json",
        "/data/office_images/abhishek.jpeg",
        "/var/ownerai.db",
    ]:
        response = client.get(path)
        assert response.status_code == 404, f"{path} returned {response.status_code}"


def test_health_endpoint_does_not_disclose_internals(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert "database" not in json.dumps(body).lower()
    assert SECRET_MARKER not in json.dumps(body)


def test_pagination_is_bounded(client, owner):
    response = owner.get("/api/events?limit=100000")
    assert response.status_code == 422


def test_cors_is_not_wildcard(client):
    response = client.get("/", headers={"Origin": "https://evil.example"})
    assert response.headers.get("Access-Control-Allow-Origin") is None
