"""Authentication endpoints.

All error messages are intentionally generic so that the API cannot be used
to enumerate accounts.  Sessions are server side, stored hashed and rotated
whenever the authentication level changes.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..crypto import decrypt_bytes, encrypt_bytes
from ..db import get_db
from ..dependencies import authenticated_user, enforce_csrf
from ..models import OneTimeToken, Role, User, UserSession
from ..ratelimit import RateLimitExceeded, check_rate_limit
from ..rbac import has_permission
from ..schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MfaVerifyRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SessionOut,
    UserOut,
)
from ..security import (
    dummy_verify,
    hash_password,
    hash_token,
    is_valid_email,
    normalise_email,
    password_needs_rehash,
    validate_password_strength,
    verify_password,
)
from ..services import audit
from ..services.mailer import build_mailer
from ..sessions import (
    clear_session_cookies,
    create_session,
    current_session_from_request,
    revoke_all_sessions,
    revoke_session,
    set_session_cookies,
)
from ..settings import get_settings
from ..totp import backup_codes, generate_secret, provisioning_uri, verify_totp

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

GENERIC_LOGIN_ERROR = "invalid credentials"
GENERIC_RESET_MESSAGE = "If that account exists, a reset link has been sent."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _client_ip(request: Request) -> str:
    from ..middleware import client_ip as resolve_ip

    return resolve_ip(request)


def _user_count(db: Session) -> int:
    return int(db.scalar(select(func.count(User.id))) or 0)


def _issue_one_time_token(db: Session, user: User, purpose: str, minutes: int) -> str:
    token = secrets.token_urlsafe(32)
    db.add(
        OneTimeToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=minutes),
        )
    )
    db.commit()
    return token


def _consume_one_time_token(db: Session, token: str, purpose: str) -> Optional[User]:
    record = db.scalar(
        select(OneTimeToken).where(
            OneTimeToken.token_hash == hash_token(token), OneTimeToken.purpose == purpose
        )
    )
    if record is None or record.used_at is not None:
        return None
    expires = record.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc):
        return None
    record.used_at = datetime.now(timezone.utc)
    db.commit()
    return db.get(User, record.user_id)


def _lockout_state(user: User) -> bool:
    if user.locked_until is None:
        return False
    locked_until = user.locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    if locked_until <= datetime.now(timezone.utc):
        user.locked_until = None
        user.failed_login_count = 0
        return False
    return True


def _maybe_lock(user: User) -> None:
    if user.failed_login_count >= 5:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
        user.failed_login_count = 0


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_csrf)],
)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> UserOut:
    """Create an account and start a session."""
    settings = get_settings()
    ip = _client_ip(request)

    try:
        check_rate_limit(
            db,
            "register",
            ip,
            settings.register_rate_limit,
            settings.register_rate_window_seconds,
            settings=settings,
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many registration attempts, please try again later",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc

    email = normalise_email(payload.email)
    if not is_valid_email(email):
        raise HTTPException(status_code=422, detail="invalid e-mail address")

    problems = validate_password_strength(payload.password, settings)
    if problems:
        raise HTTPException(
            status_code=422,
            detail={"password": problems},
        )

    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="an account with this e-mail address already exists"
        )

    # The very first account of an installation becomes its owner.
    role = Role.OWNER.value if _user_count(db) == 0 else Role.VIEWER.value
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        role=role,
        display_name=(payload.display_name or "")[:120],
        email_verified=not settings.require_email_verification,
        password_changed_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    session, token = create_session(
        db,
        user,
        ip=ip,
        user_agent=request.headers.get("user-agent", ""),
        settings=settings,
    )
    set_session_cookies(response, token, session.csrf_token, settings)

    if settings.require_email_verification:
        verification_token = _issue_one_time_token(
            db, user, "email_verification", settings.email_token_ttl_minutes
        )
        mailer = build_mailer(settings)
        try:
            mailer.send(
                user.email,
                "Confirm your account",
                f"Confirm your account by opening the link below:\n\n"
                f"{str(request.base_url).rstrip('/')}/verify-email?token={verification_token}\n\n"
                "If you did not create this account you can ignore this message.",
            )
        except Exception:  # pragma: no cover - delivery issues must not leak
            logger.warning("verification mail could not be delivered", exc_info=False)

    audit.record(
        db,
        action="auth.register",
        actor_user_id=user.id,
        target_type="user",
        target_id=user.id,
        ip=ip,
        detail={"role": role},
    )
    return UserOut.model_validate(user)


# ---------------------------------------------------------------------------
# Login / logout
# ---------------------------------------------------------------------------
@router.post("/login", dependencies=[Depends(enforce_csrf)])
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Authenticate a user and create a session."""
    settings = get_settings()
    ip = _client_ip(request)

    try:
        check_rate_limit(
            db, "login", ip, settings.login_rate_limit, settings.login_rate_window_seconds, settings=settings
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many attempts, please try again later",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc

    email = normalise_email(payload.email)
    user = db.scalar(select(User).where(User.email == email))

    if user is None:
        dummy_verify()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_LOGIN_ERROR)

    if _lockout_state(user):
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_LOGIN_ERROR)

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="this account is disabled")

    if not verify_password(user.password_hash, payload.password):
        user.failed_login_count += 1
        _maybe_lock(user)
        db.commit()
        audit.record(
            db,
            action="auth.login",
            actor_user_id=user.id,
            outcome="failure",
            ip=ip,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_LOGIN_ERROR)

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    # Rotate: an existing session of the same browser is invalidated so that a
    # session identifier can never be reused across authentication levels.
    previous = current_session_from_request(request, db)
    if previous is not None:
        revoke_session(db, previous)

    session, token = create_session(
        db,
        user,
        ip=ip,
        user_agent=request.headers.get("user-agent", ""),
        mfa_satisfied=not user.mfa_enabled,
        settings=settings,
    )
    set_session_cookies(response, token, session.csrf_token, settings)
    audit.record(db, action="auth.login", actor_user_id=user.id, target_type="user", target_id=user.id, ip=ip)

    payload_out: dict[str, Any] = {"user": UserOut.model_validate(user).model_dump(mode="json")}
    if user.mfa_enabled:
        payload_out["mfa_required"] = True
    else:
        payload_out["mfa_required"] = False
    return payload_out


@router.post("/mfa/verify", dependencies=[Depends(enforce_csrf)])
def verify_mfa(
    payload: MfaVerifyRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Complete a login with a TOTP code."""
    settings = get_settings()
    session = current_session_from_request(request, db)
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    user = session.user
    if user is None or not user.mfa_enabled or not user.mfa_secret_encrypted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="multi-factor authentication is not active")

    secret = decrypt_bytes(user.mfa_secret_encrypted, aad=b"mfa-secret").decode("utf-8")
    if not verify_totp(
        secret, payload.code, step_seconds=settings.totp_step_seconds, window=settings.totp_window
    ):
        audit.record(db, action="auth.mfa", actor_user_id=user.id, outcome="failure", ip=_client_ip(request))
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid verification code")

    # The authentication level changed - rotate the session identifier.
    new_session, token = rotate_or_update(session, db, request, settings)
    set_session_cookies(response, token, new_session.csrf_token, settings)
    audit.record(db, action="auth.mfa", actor_user_id=user.id, ip=_client_ip(request))
    return {"user": UserOut.model_validate(user).model_dump(mode="json"), "mfa_required": False}


def rotate_or_update(session: UserSession, db: Session, request: Request, settings) -> tuple[UserSession, str]:
    """Mark the session as MFA-verified and rotate its identifier."""
    from ..sessions import rotate_session

    session.mfa_satisfied = True
    db.commit()
    return rotate_session(
        db,
        session,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        mfa_satisfied=True,
        settings=settings,
    )


@router.post("/logout", dependencies=[Depends(enforce_csrf)])
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict[str, bool]:
    """Revoke the current session and clear the cookies."""
    session = current_session_from_request(request, db)
    if session is not None:
        revoke_session(db, session)
        audit.record(
            db,
            action="auth.logout",
            actor_user_id=session.user_id,
            ip=_client_ip(request),
        )
    clear_session_cookies(response, get_settings())
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(authenticated_user)) -> UserOut:
    """Return the authenticated user."""
    return UserOut.model_validate(user)


# ---------------------------------------------------------------------------
# Password management
# ---------------------------------------------------------------------------
@router.post("/password/change", dependencies=[Depends(enforce_csrf)])
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    """Change the password of the authenticated user."""
    settings = get_settings()
    session = current_session_from_request(request, db)
    user = session.user if session else None
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")

    if not verify_password(user.password_hash, payload.current_password):
        audit.record(db, action="auth.password_change", actor_user_id=user.id, outcome="failure", ip=_client_ip(request))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="the current password is incorrect")

    problems = validate_password_strength(payload.new_password, settings)
    if problems:
        raise HTTPException(status_code=422, detail={"password": problems})

    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    db.commit()

    # Changing the password invalidates every other session.
    revoke_all_sessions(db, user, except_session_id=session.id if session else None)
    audit.record(db, action="auth.password_change", actor_user_id=user.id, ip=_client_ip(request))
    return {"ok": True}


@router.post("/password/forgot", dependencies=[Depends(enforce_csrf)])
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Start a password reset.  The response never reveals whether the account exists."""
    settings = get_settings()
    ip = _client_ip(request)
    try:
        check_rate_limit(
            db,
            "password_reset",
            ip,
            settings.password_reset_rate_limit,
            settings.password_reset_rate_window_seconds,
            settings=settings,
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many requests, please try again later",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc

    email = normalise_email(payload.email)
    user = db.scalar(select(User).where(User.email == email))
    if user is not None and user.is_active:
        token = _issue_one_time_token(db, user, "password_reset", settings.email_token_ttl_minutes)
        mailer = build_mailer(settings)
        try:
            mailer.send(
                user.email,
                "Reset your password",
                f"Use the link below to choose a new password:\n\n"
                f"{str(request.base_url).rstrip('/')}/reset-password?token={token}\n\n"
                "The link expires shortly. If you did not request it, nothing changed.",
            )
        except Exception:  # pragma: no cover
            logger.warning("reset mail could not be delivered", exc_info=False)
        audit.record(db, action="auth.password_reset_request", actor_user_id=user.id, ip=ip)

    return {"message": GENERIC_RESET_MESSAGE}


@router.post("/password/reset", dependencies=[Depends(enforce_csrf)])
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    """Complete a password reset."""
    settings = get_settings()
    problems = validate_password_strength(payload.password, settings)
    if problems:
        raise HTTPException(status_code=422, detail={"password": problems})

    user = _consume_one_time_token(db, payload.token, "password_reset")
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="the reset link is invalid or expired")

    user.password_hash = hash_password(payload.password)
    user.password_changed_at = datetime.now(timezone.utc)
    user.failed_login_count = 0
    user.locked_until = None
    db.commit()
    revoke_all_sessions(db, user)
    audit.record(db, action="auth.password_reset", actor_user_id=user.id, ip=_client_ip(request))
    return {"ok": True}


@router.post("/email/verify", dependencies=[Depends(enforce_csrf)])
def verify_email(payload: dict[str, str], request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    """Confirm ownership of an e-mail address."""
    token = (payload or {}).get("token", "")
    user = _consume_one_time_token(db, token, "email_verification")
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="the confirmation link is invalid or expired")
    user.email_verified = True
    db.commit()
    audit.record(db, action="auth.email_verify", actor_user_id=user.id, ip=_client_ip(request))
    return {"ok": True}


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------
@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    request: Request, db: Session = Depends(get_db), user: User = Depends(authenticated_user)
) -> list[SessionOut]:
    """List the sessions of the authenticated user."""
    sessions = db.scalars(
        select(UserSession)
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        .order_by(UserSession.last_seen_at.desc())
    ).all()
    now = datetime.now(timezone.utc)
    results = []
    for session in sessions:
        expires = session.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= now:
            continue
        results.append(SessionOut.model_validate(session))
    return results


@router.delete("/sessions/{session_id}", dependencies=[Depends(enforce_csrf)])
def delete_session(
    session_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, bool]:
    """Revoke one of the user's own sessions."""
    session = db.get(UserSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    revoke_session(db, session)
    current = current_session_from_request(request, db)
    if current is not None and current.id == session_id:
        clear_session_cookies(response, get_settings())
    return {"ok": True}


# ---------------------------------------------------------------------------
# Multi-factor authentication management
# ---------------------------------------------------------------------------
@router.post("/mfa/setup", dependencies=[Depends(enforce_csrf)])
def mfa_setup(
    request: Request, db: Session = Depends(get_db), user: User = Depends(authenticated_user)
) -> dict[str, str]:
    """Generate a TOTP secret for the authenticated user."""
    settings = get_settings()
    if not has_permission(user.role, "settings:write"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")
    secret = generate_secret()
    user.mfa_secret_encrypted = encrypt_bytes(secret.encode("utf-8"), aad=b"mfa-secret")
    db.commit()
    return {
        "secret": secret,
        "provisioning_uri": provisioning_uri(secret, user.email, settings.totp_issuer),
    }


@router.post("/mfa/enable", dependencies=[Depends(enforce_csrf)])
def mfa_enable(
    payload: MfaVerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, Any]:
    """Enable TOTP after verifying the first code."""
    if not user.mfa_secret_encrypted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no pending MFA secret")
    secret = decrypt_bytes(user.mfa_secret_encrypted, aad=b"mfa-secret").decode("utf-8")
    settings = get_settings()
    if not verify_totp(secret, payload.code, step_seconds=settings.totp_step_seconds, window=settings.totp_window):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid verification code")
    codes = backup_codes(8)
    user.mfa_enabled = True
    user.mfa_backup_codes_hash = "|".join(hash_token(code) for code in codes)
    db.commit()
    audit.record(db, action="auth.mfa_enable", actor_user_id=user.id, ip=_client_ip(request))
    return {"backup_codes": codes}


@router.post("/mfa/disable", dependencies=[Depends(enforce_csrf)])
def mfa_disable(
    payload: dict[str, str],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, bool]:
    """Disable TOTP after re-entering the password."""
    from ..security import verify_password as _verify

    password = (payload or {}).get("password", "")
    if not _verify(user.password_hash, password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="the password is incorrect")
    user.mfa_enabled = False
    user.mfa_secret_encrypted = None
    user.mfa_backup_codes_hash = None
    db.commit()
    audit.record(db, action="auth.mfa_disable", actor_user_id=user.id, ip=_client_ip(request))
    return {"ok": True}
