"""Auth flow: bootstrap, login, sessions, CSRF, lockout, RBAC, panic, audit."""

from __future__ import annotations

OWNER = "owner@example.com"
PASSWORD = "correct horse battery staple"


def bootstrap(client):
    resp = client.post("/api/auth/bootstrap", json={
        "email": OWNER, "password": PASSWORD, "display_name": "Venki"})
    return resp


def csrf_of(client):
    return client.cookies.get("aegis_csrf", "")


def login(client, *, email=OWNER, password=PASSWORD, **kw):
    return client.post("/api/auth/login", json={
        "email": email, "password": password, **kw})


def authed(client):
    """Bootstrap owner then login; returns client."""
    resp = bootstrap(client)
    assert resp.status_code == 201, resp.text
    # fresh login exercises the normal path (bootstrap already creates a session)
    resp = login(client)
    assert resp.status_code == 200, resp.text
    return client


# ---------------------------------------------------------------- bootstrap
def test_bootstrap_only_creates_first_owner(client):
    resp = bootstrap(client)
    assert resp.status_code == 201
    assert resp.json()["role"] == "owner"
    assert resp.cookies.get("aegis_session")
    assert resp.cookies.get("aegis_csrf")

    # second attempt is refused (no account squatting)
    resp = client.post("/api/auth/bootstrap", json={
        "email": "evil@example.com", "password": PASSWORD,
        "display_name": "Evil"})
    assert resp.status_code == 403


def _set_cookie_headers(resp):
    return [v.decode() for k, v in resp.headers.raw if k == b"set-cookie"]


def test_session_cookie_is_httponly_and_csrf_is_readable(client):
    resp = bootstrap(client)
    cookies = _set_cookie_headers(resp)
    session_line = next(c for c in cookies if "aegis_session=" in c)
    csrf_line = next(c for c in cookies if "aegis_csrf=" in c)
    assert "httponly" in session_line.lower()      # session cookie: JS must not read it
    assert "httponly" not in csrf_line.lower()      # CSRF cookie: double-submit needs JS
    assert "samesite=lax" in session_line.lower()


# ------------------------------------------------------------------- /me
def test_me_requires_auth(client):
    assert client.get("/api/auth/me").status_code == 401
    authed(client)
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "owner"


def test_garbage_session_cookie_rejected(client):
    client.cookies.set("aegis_session", "deadbeef" * 4 + ".forged-secret")
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


# ------------------------------------------------------------------- login
def test_login_failure_is_generic(client):
    bootstrap(client)
    resp = login(client, password="definitely-wrong")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_credentials"


def test_login_lockout_after_repeated_failures(client):
    bootstrap(client)
    for _ in range(5):
        resp = login(client, password="definitely-wrong")
        assert resp.status_code == 401
    resp = login(client, password=PASSWORD)  # even the CORRECT password is blocked
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "rate_limited"


# ------------------------------------------------------------------- csrf
def test_mutations_require_csrf_header(client):
    authed(client)
    resp = client.post("/api/system/panic", json={"reason": "test"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "csrf_missing"

    token = csrf_of(client)
    resp = client.post("/api/system/panic", json={"reason": "test"},
                       headers={"X-CSRF-Token": token})
    assert resp.status_code == 200


def test_csrf_token_is_bound_to_session(client):
    authed(client)
    stale_token = csrf_of(client)
    # login again -> session rotated -> the old CSRF token must stop working
    assert login(client).status_code == 200
    resp = client.post("/api/system/panic", json={"reason": "x"},
                       headers={"X-CSRF-Token": stale_token})
    assert resp.status_code == 403


# ------------------------------------------------------------------- panic
def test_panic_blocks_all_but_escape_routes(client):
    authed(client)
    token = csrf_of(client)
    resp = client.post("/api/system/panic", json={"reason": "drill"},
                       headers={"X-CSRF-Token": token})
    assert resp.status_code == 200

    assert client.get("/api/auth/me").status_code == 503
    assert client.get("/healthz").status_code == 200
    assert client.post("/api/auth/login",
                       json={"email": OWNER, "password": PASSWORD}).status_code == 200
    assert client.post("/api/system/panic/clear",
                       headers={"X-CSRF-Token": csrf_of(client)}).status_code == 200
    assert client.get("/api/auth/me").status_code == 200  # unblocked again


def test_panic_requires_owner_role(client):
    authed(client)
    # forge a lower-privileged user directly (viewer)

    from backend.app.db import get_session_factory
    from backend.app.models.user import Role
    from backend.app.models.user import User as UserModel
    from backend.app.security import passwords
    factory = get_session_factory()

    async def add_viewer():
        async with factory() as session:
            session.add(UserModel(
                email="viewer@example.com",
                display_name="Viewer",
                password_hash=passwords.hash_password("a-long-viewer-passphrase"),
                role=Role.VIEWER.value))
            await session.commit()
    import asyncio as _asyncio
    _asyncio.run(add_viewer())

    assert login(client, email="viewer@example.com",
                 password="a-long-viewer-passphrase").status_code == 200
    token = csrf_of(client)
    resp = client.post("/api/system/panic", json={},
                       headers={"X-CSRF-Token": token})
    assert resp.status_code == 403  # escalated action denied


# ------------------------------------------------------------------ audit
def test_audit_chain_verifies_and_detects_tampering(client):
    authed(client)
    token = csrf_of(client)
    client.post("/api/system/panic", json={"reason": "drill"},
                headers={"X-CSRF-Token": token})
    client.post("/api/system/panic/clear", headers={"X-CSRF-Token": csrf_of(client)})

    resp = client.get("/api/system/audit/verify")
    assert resp.status_code == 200
    assert resp.json()["valid"] is True
    assert resp.json()["entries"] >= 3  # login + panic_on + panic_clear

    # tamper with an entry directly in the DB
    from sqlalchemy import text as sql_text

    from backend.app.db import get_session_factory
    factory = get_session_factory()
    import asyncio

    async def tamper():
        async with factory() as session:
            await session.execute(
                sql_text("UPDATE audit_log SET action='forged' WHERE id="
                         "(SELECT MIN(id) FROM audit_log)"))
            await session.commit()
    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(tamper())

    resp = client.get("/api/system/audit/verify")
    assert resp.json()["valid"] is False
    assert resp.json()["first_broken_id"] is not None


# --------------------------------------------------------------- validation
def test_bootstrap_input_validation(client):
    resp = client.post("/api/auth/bootstrap", json={
        "email": "not-an-email", "password": PASSWORD, "display_name": "x"})
    assert resp.status_code == 422
    resp = client.post("/api/auth/bootstrap", json={
        "email": OWNER, "password": "short", "display_name": "x"})
    assert resp.status_code == 422
    resp = client.post("/api/auth/bootstrap", json={
        "email": "extra@field.com", "password": PASSWORD,
        "display_name": "x", "role": "owner"})
    assert resp.status_code == 422  # extra fields forbidden


def test_session_secrets_never_appear_in_responses(client):
    authed(client)
    body = client.get("/api/auth/me").text
    cookie = client.cookies.get("aegis_session", "")
    secret_part = cookie.partition(".")[2]
    assert body and secret_part and secret_part not in body
