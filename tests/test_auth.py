"""Authentication and session security tests."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ownerai.db import get_engine
from ownerai.models import User, UserSession

from .conftest import auth_headers, create_user, login, register


def test_registration_requires_a_strong_password(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "weak@example.test", "password": "password"},
        headers=auth_headers(client),
    )
    assert response.status_code == 422
    assert "password" in response.json()["detail"]


def test_registration_rejects_unknown_fields(client):
    """A client must not be able to smuggle a role into the registration payload."""
    response = client.post(
        "/api/auth/register",
        json={
            "email": "sneaky@example.test",
            "password": "Correct-Horse-9!",
            "role": "owner",
            "is_admin": True,
        },
        headers=auth_headers(client),
    )
    assert response.status_code == 422
    assert "role" in response.text


def test_first_account_becomes_owner_and_second_does_not(client):
    register(client, "first@example.test")
    register(client, "second@example.test")
    with Session(get_engine()) as session:
        first = session.query(User).filter(User.email == "first@example.test").one()
        second = session.query(User).filter(User.email == "second@example.test").one()
    assert first.role == "owner"
    assert second.role != "owner"


def test_login_error_is_generic(client):
    register(client, "known@example.test")
    with Session(get_engine()) as session:
        session.query(User).filter(User.email == "known@example.test").update({"failed_login_count": 0})
        session.commit()

    unknown = client.post(
        "/api/auth/login",
        json={"email": "nobody@example.test", "password": "Wrong-Password-1!"},
        headers=auth_headers(client),
    )
    wrong = client.post(
        "/api/auth/login",
        json={"email": "known@example.test", "password": "Wrong-Password-1!"},
        headers=auth_headers(client),
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]


def test_login_is_rate_limited(client):
    register(client, "ratelimit@example.test")
    for _ in range(5):
        client.post(
            "/api/auth/login",
            json={"email": "ratelimit@example.test", "password": "Wrong-Password-1!"},
            headers=auth_headers(client),
        )
    blocked = client.post(
        "/api/auth/login",
        json={"email": "ratelimit@example.test", "password": "Wrong-Password-1!"},
        headers=auth_headers(client),
    )
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_registration_is_rate_limited(client):
    for index in range(3):
        response = client.post(
            "/api/auth/register",
            json={"email": f"user{index}@example.test", "password": "Correct-Horse-9!"},
            headers=auth_headers(client),
        )
        assert response.status_code == 201
    blocked = client.post(
        "/api/auth/register",
        json={"email": "user3@example.test", "password": "Correct-Horse-9!"},
        headers=auth_headers(client),
    )
    assert blocked.status_code == 429


def test_logout_invalidates_the_session(client):
    register(client)
    login(client)
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout", headers=auth_headers(client)).status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_login_rotates_the_session_identifier(client):
    register(client)
    login(client)
    with Session(get_engine()) as session:
        first = session.query(UserSession).order_by(UserSession.id.desc()).first()
        first_hash = first.token_hash
    login(client)
    with Session(get_engine()) as session:
        sessions = session.query(UserSession).order_by(UserSession.id.desc()).all()
        assert sessions[0].token_hash != first_hash
        assert sessions[1].revoked_at is not None


def test_expired_session_cannot_access_protected_resources(client):
    register(client)
    login(client)
    with Session(get_engine()) as session:
        record = session.query(UserSession).order_by(UserSession.id.desc()).first()
        record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        session.commit()
    assert client.get("/api/auth/me").status_code == 401


def test_revoked_session_cannot_access_protected_resources(client):
    register(client)
    login(client)
    with Session(get_engine()) as session:
        record = session.query(UserSession).order_by(UserSession.id.desc()).first()
        record.revoked_at = datetime.now(timezone.utc)
        session.commit()
    assert client.get("/api/auth/me").status_code == 401


def test_changing_the_password_revokes_other_sessions(client):
    register(client)
    login(client)
    response = client.post(
        "/api/auth/password/change",
        json={"current_password": "Correct-Horse-9!", "new_password": "Even-Better-Secret-7!"},
        headers=auth_headers(client),
    )
    assert response.status_code == 200
    sessions = client.get("/api/auth/sessions").json()
    assert len(sessions) <= 1


def test_password_reset_token_can_only_be_used_once(client):
    register(client, "reset@example.test")
    from ownerai.routers import auth as auth_router

    # Capture the token that would be mailed.
    sent: list[str] = []

    class CaptureMailer:
        def send(self, recipient, subject, body):
            sent.append(body)
            return True

    original = auth_router.build_mailer
    auth_router.build_mailer = lambda settings=None: CaptureMailer()  # type: ignore[assignment]
    try:
        client.post(
            "/api/auth/password/forgot",
            json={"email": "reset@example.test"},
            headers=auth_headers(client),
        )
    finally:
        auth_router.build_mailer = original  # type: ignore[assignment]

    assert sent, "a reset mail should have been generated"
    token = sent[0].split("token=")[1].split()[0]

    first = client.post(
        "/api/auth/password/reset",
        json={"token": token, "password": "Brand-New-Secret-8!"},
        headers=auth_headers(client),
    )
    assert first.status_code == 200
    second = client.post(
        "/api/auth/password/reset",
        json={"token": token, "password": "Brand-New-Secret-9!"},
        headers=auth_headers(client),
    )
    assert second.status_code == 400


def test_password_reset_does_not_leak_account_existence(client):
    register(client, "exists@example.test")
    known = client.post(
        "/api/auth/password/forgot",
        json={"email": "exists@example.test"},
        headers=auth_headers(client),
    )
    unknown = client.post(
        "/api/auth/password/forgot",
        json={"email": "does-not-exist@example.test"},
        headers=auth_headers(client),
    )
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()


def test_state_changing_requests_require_a_csrf_token(client):
    register(client)
    login(client)
    response = client.post("/api/devices", json={"name": "cam", "device_type": "webcam"})
    assert response.status_code == 403


def test_state_changing_requests_reject_a_forged_csrf_token(client):
    register(client)
    login(client)
    response = client.post(
        "/api/devices",
        json={"name": "cam", "device_type": "webcam"},
        headers={"X-CSRF-Token": "forged-token"},
    )
    assert response.status_code == 403


def test_session_cookie_is_http_only_and_not_in_local_storage(client):
    """The session token must be an HttpOnly cookie and never reach the JS storage."""
    register(client)
    response = client.post(
        "/api/auth/login",
        json={"email": "owner@example.test", "password": "Correct-Horse-9!"},
        headers=auth_headers(client),
    )
    assert response.status_code == 200
    cookies = response.headers.get_list("set-cookie")
    session_cookie = next((item for item in cookies if item.startswith("ownerai_session=")), None)
    csrf_cookie = next((item for item in cookies if item.startswith("ownerai_csrf=")), None)
    assert session_cookie is not None
    assert "httponly" in session_cookie.lower()
    assert "samesite=lax" in session_cookie.lower()
    # The CSRF token is intentionally readable by the front-end, the session
    # token is not.
    assert csrf_cookie is not None
    assert "httponly" not in csrf_cookie.lower()

    # No front-end file may persist the session token.
    import pathlib

    static_dir = pathlib.Path(__file__).resolve().parent.parent / "ownerai" / "static"
    for path in static_dir.rglob("*.js"):
        content = path.read_text(encoding="utf-8")
        assert "ownerai_session" not in content
        assert "sessionStorage" not in content
        # localStorage may only be used for the theme preference.
        for match in re.findall(r"localStorage\.\w+\(([^)]*)\)", content):
            assert "THEME_KEY" in match or "theme" in match.lower()


def test_disabled_account_cannot_sign_in(client):
    user_id = create_user("disabled@example.test", role="viewer")
    with Session(get_engine()) as session:
        session.get(User, user_id).is_active = False
        session.commit()
    response = client.post(
        "/api/auth/login",
        json={"email": "disabled@example.test", "password": "Correct-Horse-9!"},
        headers=auth_headers(client),
    )
    assert response.status_code == 403
