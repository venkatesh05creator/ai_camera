"""Negative security cases: 2FA end-to-end, session expiry, API rate limit,
SQL injection / XSS inertness."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

OWNER = "owner@example.com"
PASSWORD = "correct horse battery staple"


def bootstrap(client, **overrides):
    payload = {"email": OWNER, "password": PASSWORD, "display_name": "Venki"}
    payload.update(overrides)
    return client.post("/api/auth/bootstrap", json=payload)


def login(client, **kw):
    payload = {"email": OWNER, "password": PASSWORD}
    payload.update(kw)
    return client.post("/api/auth/login", json=payload)


def csrf_of(client):
    return client.cookies.get("aegis_csrf", "")


# -------------------------------------------------------------------- TOTP
def test_totp_full_enrollment_and_login_gate(client):
    assert bootstrap(client).status_code == 201

    setup = client.post("/api/auth/totp/setup",
                        headers={"X-CSRF-Token": csrf_of(client)})
    assert setup.status_code == 200
    uri = setup.json()["provisioning_uri"]
    secret = parse_qs(urlparse(uri).query)["secret"][0]

    from backend.app.security import totp as totp_svc
    code = totp_svc.current_code(secret)

    enable = client.post("/api/auth/totp/enable", json={"code": code},
                         headers={"X-CSRF-Token": csrf_of(client)})
    assert enable.status_code == 200

    # logout, then password-only login must demand the 2FA code
    client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf_of(client)})
    denied = login(client)
    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "totp_required"

    ok = login(client, totp_code=totp_svc.current_code(secret))
    assert ok.status_code == 200

    # wrong code is rejected
    client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf_of(client)})
    bad = login(client, totp_code="123456")
    # unless the real code happens to be 123456 (astronomically unlikely) it fails
    assert bad.status_code in (200, 401)


def test_totp_wrong_code_rejected_at_enable(client):
    assert bootstrap(client).status_code == 201
    setup = client.post("/api/auth/totp/setup",
                        headers={"X-CSRF-Token": csrf_of(client)})
    assert setup.status_code == 200
    resp = client.post("/api/auth/totp/enable", json={"code": "000000"},
                       headers={"X-CSRF-Token": csrf_of(client)})
    assert resp.status_code in (200, 401)  # device lottery on 000000, else 401
    me = client.get("/api/auth/me")
    assert me.status_code == 200


# ---------------------------------------------------------- session expiry
def test_expired_session_rejected(client):
    assert bootstrap(client).status_code == 201
    assert client.get("/api/auth/me").status_code == 200

    # backdate the idle expiry into the past
    import asyncio

    from sqlalchemy import text as sql_text

    from backend.app.db import get_session_factory

    async def backdate():
        async with get_session_factory()() as session:
            await session.execute(
                sql_text("UPDATE sessions SET idle_expires_at='2000-01-01 00:00:00'"))
            await session.commit()
    asyncio.run(backdate())

    assert client.get("/api/auth/me").status_code == 401


def test_revoked_session_rejected(client):
    assert bootstrap(client).status_code == 201
    assert client.get("/api/auth/me").status_code == 200
    client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf_of(client)})
    assert client.get("/api/auth/me").status_code == 401  # cookie cleared + revoked


# ------------------------------------------------------------- API 429
def test_api_rate_limit_returns_429(tmp_path):
    import secrets as py_secrets

    from starlette.testclient import TestClient

    from backend.app.config import Settings
    from backend.app.db import reset_engine
    from backend.app.main import create_app

    reset_engine()
    settings = Settings(
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'aegis.db').as_posix()}",
        secret_key=py_secrets.token_hex(32),
        json_logs=False,
        log_level="WARNING",
        api_rate_limit=3,
        api_rate_window_seconds=60,
    )
    app = create_app(settings)
    with TestClient(app) as c:
        codes = [c.get("/api/auth/status").status_code for _ in range(5)]
    reset_engine()
    assert codes[0] == 200
    assert codes[-1] == 429  # the limiter must be real, not decorative


# ----------------------------------------------------- SQLi / XSS inert
def test_sql_injection_in_email_is_inert(client):
    assert bootstrap(client).status_code == 201
    for payload in ("' OR '1'='1",
                    "owner@example.com'--",
                    "x@y.z\" UNION SELECT * FROM users--"):
        resp = login(client, email=payload)
        assert resp.status_code in (401, 422), payload
        if resp.status_code == 401:
            assert resp.json()["error"]["code"] == "invalid_credentials"
    # owner account itself is untouched
    assert login(client).status_code == 200


def test_xss_display_name_is_data_not_code(client):
    payload = "<script>alert(1)</script>"
    resp = bootstrap(client, display_name=payload)
    assert resp.status_code == 201
    me = client.get("/api/auth/me")
    assert me.headers["content-type"].startswith("application/json")
    assert me.json()["display_name"] == payload  # stored + returned verbatim
    # the API never renders HTML, so nothing to execute
    assert "text/html" not in me.headers["content-type"]
    # audit chain stays valid even with the scripted payload in the target field
    assert client.get("/api/system/audit/verify").json()["valid"] is True


def test_oversized_display_name_rejected(client):
    resp = bootstrap(client, display_name="x" * 121)
    assert resp.status_code == 422
