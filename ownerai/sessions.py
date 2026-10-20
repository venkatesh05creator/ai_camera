"""Session lifecycle, cookie handling and CSRF validation."""

from __future__ import annotations

import hashlib
import logging
from datetime import timedelta
from typing import Optional, Tuple

from fastapi import HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .crypto import constant_time_equals
from .models import User, UserSession
from .security import (
    as_utc,
    hash_token,
    is_expired,
    new_csrf_token,
    new_session_token,
    session_lifetime,
    sign_csrf_token,
    utcnow,
    verify_signed_csrf_token,
)
from .settings import Settings, get_settings

logger = logging.getLogger(__name__)

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


# ---------------------------------------------------------------------------
# Creation / revocation
# ---------------------------------------------------------------------------
def create_session(
    db: Session,
    user: User,
    *,
    ip: str = "",
    user_agent: str = "",
    mfa_satisfied: bool = False,
    remember: bool = False,
    settings: Optional[Settings] = None,
) -> Tuple[UserSession, str]:
    """Create a new server-side session and return it with its bearer token."""
    settings = settings or get_settings()
    token = new_session_token()
    lifetime = session_lifetime(settings)
    absolute = lifetime.absolute_expires_at
    if remember:
        absolute = utcnow() + timedelta(days=settings.remember_me_days)

    session = UserSession(
        user_id=user.id,
        token_hash=hash_token(token),
        csrf_token=new_csrf_token(),
        created_at=utcnow(),
        last_seen_at=utcnow(),
        expires_at=lifetime.expires_at,
        absolute_expires_at=absolute,
        mfa_satisfied=mfa_satisfied,
        ip_hash=_hash_ip(ip),
        user_agent_hash=hashlib.sha256((user_agent or "").encode("utf-8")).hexdigest(),
        user_agent=(user_agent or "")[:256],
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session, token


def rotate_session(
    db: Session,
    old_session: UserSession,
    *,
    ip: str = "",
    user_agent: str = "",
    mfa_satisfied: Optional[bool] = None,
    settings: Optional[Settings] = None,
) -> Tuple[UserSession, str]:
    """Invalidate a session and issue a fresh one (session fixation defence)."""
    settings = settings or get_settings()
    if old_session is not None:
        old_session.revoked_at = utcnow()
        db.commit()
    user = old_session.user
    return create_session(
        db,
        user,
        ip=ip,
        user_agent=user_agent,
        mfa_satisfied=old_session.mfa_satisfied if mfa_satisfied is None else mfa_satisfied,
        settings=settings,
    )


def revoke_session(db: Session, session: UserSession) -> None:
    """Revoke a single session."""
    if session.revoked_at is None:
        session.revoked_at = utcnow()
        db.commit()


def revoke_all_sessions(db: Session, user: User, *, except_session_id: Optional[int] = None) -> int:
    """Revoke every session of a user (used on password change and logout-everywhere)."""
    sessions = db.scalars(select(UserSession).where(UserSession.user_id == user.id)).all()
    count = 0
    for session in sessions:
        if session.revoked_at is None and session.id != except_session_id:
            session.revoked_at = utcnow()
            count += 1
    db.commit()
    return count


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------
def current_session_from_request(request: Request, db: Session) -> Optional[UserSession]:
    """Return the active session for the request, or ``None``."""
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    if session is None:
        return None
    if session.revoked_at is not None:
        return None
    if is_expired(session.expires_at) or is_expired(session.absolute_expires_at):
        session.revoked_at = utcnow()
        db.commit()
        return None
    user = session.user
    if user is None or not user.is_active:
        return None
    now = utcnow()
    last_seen = as_utc(session.last_seen_at) or now
    if (now - last_seen) > timedelta(seconds=settings.session_idle_minutes * 60):
        session.revoked_at = now
        db.commit()
        return None
    session.last_seen_at = now
    return session


def current_user_from_request(request: Request, db: Session) -> Optional[User]:
    """Return the authenticated user for the request, or ``None``."""
    session = current_session_from_request(request, db)
    if session is None:
        return None
    return session.user


def session_from_token(db: Session, token: str) -> Optional[UserSession]:
    """Look up a session by its bearer token (used by the WebSocket handler)."""
    if not token:
        return None
    session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    if session is None or session.revoked_at is not None:
        return None
    if is_expired(session.expires_at) or is_expired(session.absolute_expires_at):
        return None
    return session


# ---------------------------------------------------------------------------
# Cookies
# ---------------------------------------------------------------------------
def set_session_cookies(
    response: Response,
    token: str,
    csrf_token: str,
    settings: Optional[Settings] = None,
) -> None:
    """Attach the session and CSRF cookies to a response."""
    settings = settings or get_settings()
    max_age = settings.session_absolute_minutes * 60
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.secure_cookies,
        samesite=settings.cookie_samesite,
        path="/",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        max_age=max_age,
        httponly=False,  # readable by the front-end so it can echo it back
        secure=settings.secure_cookies,
        samesite=settings.cookie_samesite,
        path="/",
    )


def clear_session_cookies(response: Response, settings: Optional[Settings] = None) -> None:
    """Remove the session and CSRF cookies."""
    settings = settings or get_settings()
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")


def ensure_csrf_cookie(
    request: Request,
    response: Response,
    settings: Optional[Settings] = None,
    session: Optional[UserSession] = None,
) -> str:
    """Guarantee that a visitor owns a usable CSRF token.

    * Authenticated visitors receive the CSRF token that is bound to their
      session (the cookie must always mirror the session token).
    * Anonymous visitors (login/registration forms) receive a token that is
      signed by the server secret, which cannot be forged by another site.
    """
    settings = settings or get_settings()
    cookie_name = settings.csrf_cookie_name

    if session is not None:
        expected = session.csrf_token
        if request.cookies.get(cookie_name) != expected:
            response.set_cookie(
                cookie_name,
                expected,
                max_age=settings.session_absolute_minutes * 60,
                httponly=False,
                secure=settings.secure_cookies,
                samesite=settings.cookie_samesite,
                path="/",
            )
        return expected

    existing = request.cookies.get(cookie_name)
    if existing and verify_signed_csrf_token(existing, settings):
        return existing
    nonce = new_csrf_token()
    signed = sign_csrf_token(nonce, settings)
    response.set_cookie(
        cookie_name,
        signed,
        max_age=settings.session_absolute_minutes * 60,
        httponly=False,
        secure=settings.secure_cookies,
        samesite=settings.cookie_samesite,
        path="/",
    )
    return signed


# ---------------------------------------------------------------------------
# CSRF validation
# ---------------------------------------------------------------------------
async def extract_csrf_token(request: Request) -> str:
    """Read the CSRF token from the header or the submitted form."""
    header = request.headers.get("x-csrf-token")
    if header:
        return header
    content_type = request.headers.get("content-type", "")
    if content_type.startswith(("application/x-www-form-urlencoded", "multipart/form-data")):
        try:
            form = await request.form()
        except Exception:  # pragma: no cover - malformed body
            return ""
        value = form.get("csrf_token")
        return str(value) if value else ""
    return ""


async def validate_csrf(request: Request, db: Session, session: Optional[UserSession]) -> None:
    """Validate the CSRF token of a state-changing request.

    * Authenticated requests must echo the session bound token.
    * Anonymous requests must echo a token signed by the server.
    """
    if request.method in SAFE_METHODS:
        return

    settings = get_settings()
    submitted = await extract_csrf_token(request)
    if not submitted:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="missing CSRF token")

    if session is not None:
        if constant_time_equals(submitted, session.csrf_token):
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid CSRF token")

    if verify_signed_csrf_token(submitted, settings):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid CSRF token")


def _hash_ip(ip: str) -> str:
    if not ip:
        return ""
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()
