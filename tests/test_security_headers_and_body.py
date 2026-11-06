"""Security headers, request-body limit, error handling, HTTPS enforcement."""

from __future__ import annotations

from backend.app.config import Settings


def test_security_headers_present(client):
    resp = client.get("/healthz")
    csp = resp.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "base-uri 'none'" in csp
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["referrer-policy"] == "no-referrer"
    assert resp.headers["permissions-policy"] == "camera=(self), microphone=(self), geolocation=()"
    assert resp.headers["x-request-id"]  # every response carries a request id
    # no HSTS on plain http in test env
    assert "strict-transport-security" not in resp.headers


def test_oversized_body_rejected_413(client):
    # exceed the *configured* limit (env may raise it above the 1MB default)
    limit = client.app.state.settings.max_request_body_bytes
    big = b"x" * (limit + 100_000)
    resp = client.post("/healthz", content=big,
                       headers={"content-type": "application/octet-stream"})
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "payload_too_large"


def test_unknown_route_returns_json_404(client):
    resp = client.get("/definitely-not-a-route")
    assert resp.status_code == 404
    assert "text/json" in resp.headers["content-type"] or \
        resp.headers["content-type"].startswith("application/json")


def test_https_only_redirects():
    import secrets

    from starlette.testclient import TestClient

    from backend.app.db import reset_engine
    from backend.app.main import create_app

    reset_engine()
    settings = Settings(
        app_env="test",
        https_only=True,
        secret_key=secrets.token_hex(32),
        json_logs=False,
        log_level="WARNING",
        hsts_enabled=False,
    )
    app = create_app(settings)
    with TestClient(app) as c:
        resp = c.get("/healthz")  # http://testserver -> must NOT be served over http
        assert resp.status_code == 426
        assert resp.headers["location"].startswith("https://")
    reset_engine()
