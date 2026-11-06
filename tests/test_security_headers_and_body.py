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
    # inside the API namespace unknown paths are JSON 404 (page paths are SPA-served)
    resp = client.get("/api/definitely-not-a-route")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json()["error"]["code"] == "not_found"


def test_spa_fallback_serves_index_and_assets(tmp_path, monkeypatch):
    """With a built web/dist, page routes serve the PWA, API stays JSON."""
    import secrets
    from pathlib import Path

    from starlette.testclient import TestClient

    from backend.app.db import reset_engine
    from backend.app.main import create_app

    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>Aegis</title>", encoding="utf-8")
    (assets / "app.js").write_text("console.log('spa');", encoding="utf-8")
    monkeypatch.setenv("AEGIS_WEB_DIST", str(dist))

    reset_engine()
    settings = Settings(
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'aegis.db').as_posix()}",
        secret_key=secrets.token_hex(32),
        json_logs=False,
        log_level="WARNING",
    )
    app = create_app(settings)
    with TestClient(app) as c:
        root = c.get("/")
        assert root.status_code == 200
        assert "Aegis" in root.text
        deep = c.get("/some/client/route")
        assert deep.status_code == 200
        assert "Aegis" in deep.text  # SPA fallback, not a 404
        asset = c.get("/assets/app.js")
        assert asset.status_code == 200
        assert "console.log" in asset.text
        api_miss = c.get("/api/nope")
        assert api_miss.status_code == 404
        assert api_miss.json()["error"]["code"] == "not_found"
        health = c.get("/healthz")
        assert health.status_code == 200  # explicit route still wins
    reset_engine()
    assert (Path(dist) / "index.html").exists()  # never served from outside dist


def test_https_only_redirects(tmp_path):
    import pathlib
    import secrets
    import tempfile

    from starlette.testclient import TestClient

    from backend.app.db import reset_engine
    from backend.app.main import create_app

    reset_engine()
    settings = Settings(
        app_env="test",
        https_only=True,
        secret_key=secrets.token_hex(32),
        database_url=f"sqlite+aiosqlite:///{(pathlib.Path(tempfile.mkdtemp(prefix='aegis-https-')) / 'aegis.db').as_posix()}",
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
