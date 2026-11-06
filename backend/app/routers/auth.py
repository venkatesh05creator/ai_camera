"""Authentication routes: bootstrap, login, logout, me, TOTP enrollment."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from ..config import Settings
from ..dependencies import DbDep, require_csrf, require_user
from ..models.session import Session as SessionRow
from ..models.user import User
from ..schemas import (
    BootstrapIn,
    LoginIn,
    MeOut,
    StatusOut,
    TotpIn,
    TotpSetupOut,
)
from ..security import totp as totp_svc
from ..security.crypto import CryptoError, decrypt_text, encrypt_text
from ..services import audit_service, auth_service
from ..services.auth_service import AuthError

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _auth_error_response(exc: AuthError) -> dict[str, dict[str, str]]:
    return {"error": {"code": exc.code, "message": exc.message}}


def _set_session_cookies(
    response: Response,
    settings: Settings,
    session_id: str,
    secret: str,
    csrf_token: str,
    *, remember_me: bool = False,
) -> None:
    secure = settings.https_only or settings.app_env == "production"
    max_age = (settings.remember_me_hours * 3600 if remember_me
               else settings.session_absolute_minutes * 60)
    response.set_cookie(
        settings.cookie_session_name, f"{session_id}.{secret}",
        httponly=True, secure=secure,
        samesite=settings.cookie_samesite, max_age=max_age, path="/",
    )
    # CSRF cookie is deliberately readable by the frontend JS (double submit)
    response.set_cookie(
        settings.cookie_csrf_name, csrf_token,
        httponly=False, secure=secure,
        samesite=settings.cookie_samesite, max_age=max_age, path="/",
    )


def _clear_session_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(settings.cookie_session_name, path="/")
    response.delete_cookie(settings.cookie_csrf_name, path="/")


def _ip(request: Request) -> str:
    return request.client.host if request.client else ""


@router.get("/status", response_model=StatusOut)
async def status(db: DbDep, request: Request) -> StatusOut:
    needs = await auth_service.user_count(db) == 0
    return StatusOut(
        needs_bootstrap=needs,
        app_env=request.app.state.settings.app_env,
        panic_active=bool(request.app.state.panic.get("active", False)),
    )


@router.post("/bootstrap", response_model=MeOut, status_code=201)
async def bootstrap(
    body: BootstrapIn,
    request: Request,
    response: Response,
    db: DbDep,
) -> MeOut:
    settings: Settings = request.app.state.settings
    cred = await auth_service.bootstrap_owner(
        db, settings, email=body.email, password=body.password,
        display_name=body.display_name)
    _set_session_cookies(response, settings, cred.session.id, cred.secret,
                         cred.session.csrf_token)
    await audit_service.record(
        db, "auth.bootstrap", actor_user_id=cred.user.id,
        target=f"user#{cred.user.id}")
    await db.commit()
    return MeOut(
        id=cred.user.id, email=cred.user.email,
        display_name=cred.user.display_name, role=cred.user.role,
        totp_enabled=cred.user.totp_enabled)


@router.post("/login", response_model=MeOut)
async def login(
    body: LoginIn, request: Request, response: Response, db: DbDep
) -> MeOut:
    settings: Settings = request.app.state.settings
    try:
        cred = await auth_service.login(
            db, settings, email=body.email, password=body.password,
            ip=_ip(request),
            user_agent=request.headers.get("user-agent", ""),
            remember_me=body.remember_me, totp_code=body.totp_code)
    except AuthError:
        await db.commit()  # persist the failed-attempt counters
        raise
    _set_session_cookies(
        response, settings, cred.session.id, cred.secret,
        cred.session.csrf_token, remember_me=body.remember_me)
    await audit_service.record(
        db, "auth.login", actor_user_id=cred.user.id,
        detail={"remember_me": body.remember_me})
    await db.commit()
    return MeOut(
        id=cred.user.id, email=cred.user.email,
        display_name=cred.user.display_name, role=cred.user.role,
        totp_enabled=cred.user.totp_enabled)


@router.post("/logout", response_model=dict)
async def logout(
    request: Request,
    response: Response,
    pair: Annotated[tuple[User, SessionRow], Depends(require_csrf)],
    db: DbDep,
) -> dict:
    user, row = pair
    await auth_service.revoke_session(db, row)
    _clear_session_cookies(response, request.app.state.settings)
    await audit_service.record(db, "auth.logout", actor_user_id=user.id)
    await db.commit()
    return {"ok": True}


@router.get("/me", response_model=MeOut)
async def me(
    pair: Annotated[tuple[User, SessionRow], Depends(require_user)]
) -> MeOut:
    user, _row = pair
    return MeOut(
        id=user.id, email=user.email, display_name=user.display_name,
        role=user.role, totp_enabled=user.totp_enabled)


def _decrypt_totp_secret(settings: Settings, encrypted: str) -> str:
    try:
        return decrypt_text(auth_service._totp_key(settings), encrypted)
    except CryptoError as exc:
        raise AuthError("totp_not_setup", "run /totp/setup first",
                        status=409) from exc


@router.post("/totp/setup", response_model=TotpSetupOut)
async def totp_setup(
    pair: Annotated[tuple[User, SessionRow], Depends(require_csrf)],
    db: DbDep,
    request: Request,
) -> TotpSetupOut:
    user, _row = pair
    if user.totp_enabled:
        raise AuthError("totp_enabled", "2FA already enabled", status=409)
    secret = totp_svc.new_secret()
    user.totp_secret_encrypted = encrypt_text(
        auth_service._totp_key(request.app.state.settings), secret)
    await audit_service.record(db, "auth.totp_setup", actor_user_id=user.id)
    await db.commit()
    return TotpSetupOut(
        provisioning_uri=totp_svc.provisioning_uri(secret, user.email))


@router.post("/totp/enable", response_model=dict)
async def totp_enable(
    body: TotpIn,
    pair: Annotated[tuple[User, SessionRow], Depends(require_csrf)],
    db: DbDep,
    request: Request,
) -> dict:
    user, _row = pair
    settings = request.app.state.settings
    if user.totp_enabled:
        raise AuthError("totp_enabled", "2FA already enabled", status=409)
    if not user.totp_secret_encrypted:
        raise AuthError("totp_not_setup", "run /totp/setup first", status=409)
    secret = _decrypt_totp_secret(settings, user.totp_secret_encrypted)
    if not totp_svc.verify_code(secret, body.code):
        raise AuthError("totp_invalid", "invalid code", status=401)
    user.totp_enabled = True
    await audit_service.record(db, "auth.totp_enabled", actor_user_id=user.id)
    await db.commit()
    return {"ok": True}


@router.post("/totp/disable", response_model=dict)
async def totp_disable(
    body: TotpIn,
    pair: Annotated[tuple[User, SessionRow], Depends(require_csrf)],
    db: DbDep,
    request: Request,
) -> dict:
    user, _row = pair
    settings = request.app.state.settings
    if not user.totp_enabled or not user.totp_secret_encrypted:
        raise AuthError("totp_not_enabled", "2FA not enabled", status=409)
    secret = _decrypt_totp_secret(settings, user.totp_secret_encrypted)
    if not totp_svc.verify_code(secret, body.code):
        raise AuthError("totp_invalid", "invalid code", status=401)
    user.totp_enabled = False
    user.totp_secret_encrypted = ""  # nosec B105
    await audit_service.record(db, "auth.totp_disabled", actor_user_id=user.id)
    await db.commit()
    return {"ok": True}
