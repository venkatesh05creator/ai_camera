"""Authentication & session management.

- first account becomes owner (bootstrap)
- Argon2id password verification
- server-side sessions: opaque cookie ``session_id.secret``, secret stored
  hashed (SHA-256), idle + absolute expiry, rotation, revocation
- lockout on repeated login failures (bucket = identifier|ip)
- CSRF token bound to the session, delivered via a non-HttpOnly cookie
- TOTP 2FA enforced at login when enabled
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..models.session import Session as SessionRow
from ..models.user import Role, User, utcnow
from ..security import passwords
from ..security import totp as totp_svc
from ..security.crypto import CryptoError, decrypt_text, derive_key
from . import rate_limit


class AuthError(Exception):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


@dataclass(frozen=True)
class Credentials:
    user: User
    session: SessionRow
    secret: str = field(default="")  # once-only cookie material


def _totp_key(settings: Settings) -> bytes:
    """32-byte key for TOTP-secret encryption (config-driven)."""
    material = (settings.biometric_encryption_key.get_secret_value()
                or settings.secret_key.get_secret_value()
                or "aegis-dev-key")
    return derive_key(material)


# ---------------------------------------------------------------- bootstrap
async def user_count(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count(User.id))) or 0)


async def bootstrap_owner(
    session: AsyncSession,
    settings: Settings,
    *,
    email: str,
    password: str,
    display_name: str,
) -> Credentials:
    """Create the first (owner) account. Refuses when accounts already exist."""
    if await user_count(session) > 0:
        raise AuthError("forbidden", "an account already exists on this system",
                        status=403)
    weakness = passwords.password_strength_error(password)
    if weakness:
        raise AuthError("weak_password", weakness, status=422)
    user = User(
        email=email.strip().lower(),
        display_name=display_name.strip()[:120],
        password_hash=passwords.hash_password(password),
        role=Role.OWNER.value,
    )
    session.add(user)
    await session.flush()
    return await _issue_credentials(session, settings, user)


# -------------------------------------------------------------------- login
async def login(
    session: AsyncSession,
    settings: Settings,
    *,
    email: str,
    password: str,
    ip: str = "",
    user_agent: str = "",
    remember_me: bool = False,
    totp_code: str = "",
) -> Credentials:
    email = email.strip().lower()
    if await rate_limit.login_locked_out(
            session, email, ip,
            max_failures=settings.login_rate_limit,
            lockout_minutes=settings.login_lockout_minutes):
        raise AuthError("rate_limited", "too many failed attempts; try later",
                        status=429)

    user = (await session.execute(
        select(User).where(User.email == email))).scalar_one_or_none()
    password_ok = user is not None and user.is_active and \
        passwords.verify_password(user.password_hash, password)

    if not password_ok:
        await rate_limit.record_login_failure(session, email, ip)
        # generic failure message: never reveal whether the account exists
        raise AuthError("invalid_credentials",
                        "invalid email or password", status=401)
    if user is None or not user.is_active:  # pragma: no cover - defensive
        raise AuthError("invalid_credentials",
                        "invalid email or password", status=401)

    if user.totp_enabled:
        try:
            secret = decrypt_text(_totp_key(settings), user.totp_secret_encrypted)
        except CryptoError as exc:
            raise AuthError("server_error", "could not verify 2FA", 500) from exc
        if not (totp_code and totp_svc.verify_code(secret, totp_code)):
            raise AuthError("totp_required", "two-factor code required", status=401)

    cred = await _issue_credentials(session, settings, user, remember_me=remember_me)
    cred.session.ip = ip[:64]
    cred.session.user_agent = (user_agent or "")[:300]
    return cred


# ------------------------------------------------------------------ sessions
async def _issue_credentials(
    session: AsyncSession,
    settings: Settings,
    user: User,
    *,
    remember_me: bool = False,
    rotated_from: str | None = None,
) -> Credentials:
    session_secret = secrets.token_urlsafe(32)
    absolute_hours = (settings.remember_me_hours if remember_me
                      else settings.session_absolute_minutes / 60)
    row = SessionRow(
        id=uuid.uuid4().hex,
        user_id=user.id,
        secret_hash=hashlib.sha256(session_secret.encode()).hexdigest(),
        csrf_token=secrets.token_urlsafe(32),
        rotated_from=rotated_from,
        created_at=utcnow(),
        last_seen_at=utcnow(),
        idle_expires_at=utcnow() + timedelta(minutes=settings.session_idle_minutes),
        absolute_expires_at=utcnow() + timedelta(hours=absolute_hours),
    )
    session.add(row)
    await session.flush()
    return Credentials(user=user, session=row, secret=session_secret)


# ------------------------------------------------------------------ lookup
async def get_valid_session(
    session: AsyncSession,
    settings: Settings,
    cookie_token: str,
    *,
    touch: bool = True,
) -> tuple[User, SessionRow, str] | None:
    """Validate the cookie token; return (user, session, secret) or None."""
    sid, _, secret = cookie_token.partition(".")
    if not sid or not secret or len(sid) != 32:
        return None
    row = (await session.execute(
        select(SessionRow).where(SessionRow.id == sid))).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        return None
    if not hmac.compare_digest(
            hashlib.sha256(secret.encode()).hexdigest(), row.secret_hash):
        return None
    now = utcnow()
    if now >= row.absolute_expires_at or now >= row.idle_expires_at:
        return None
    user = (await session.execute(
        select(User).where(User.id == row.user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    if touch:
        row.last_seen_at = now
        row.idle_expires_at = now + timedelta(
            minutes=settings.session_idle_minutes)
    return user, row, secret


async def rotate_session(
    session: AsyncSession,
    settings: Settings,
    current: SessionRow,
) -> Credentials:
    """New credentials for the same user; the old session is revoked."""
    user = await session.get(User, current.user_id)
    if user is None:  # pragma: no cover - defensive
        raise AuthError("server_error", "user vanished", 500)
    cred = await _issue_credentials(session, settings, user, rotated_from=current.id)
    await revoke_session(session, current)
    return cred


async def revoke_session(session: AsyncSession, row: SessionRow) -> None:
    row.revoked_at = utcnow()


async def revoke_all_for_user(session: AsyncSession, user_id: int,
                              *, except_session_id: str = "") -> int:
    stmt = update(SessionRow).where(
        SessionRow.user_id == user_id,
        SessionRow.revoked_at.is_(None))
    if except_session_id:
        stmt = stmt.where(SessionRow.id != except_session_id)
    result = await session.execute(stmt.values(revoked_at=utcnow()))
    rowcount = getattr(result, "rowcount", 0)  # CursorResult carries rowcount
    return int(rowcount or 0)


# ------------------------------------------------------------------ creation
async def create_user(
    session: AsyncSession,
    settings: Settings,
    *,
    email: str,
    password: str,
    display_name: str,
    role: Role,
) -> User:
    """Owner tool for creating additional accounts (lower roles)."""
    if role == Role.OWNER:
        raise AuthError("forbidden", "cannot create a second owner via API",
                        status=403)
    weakness = passwords.password_strength_error(password)
    if weakness:
        raise AuthError("weak_password", weakness, status=422)
    existing = (await session.execute(
        select(User).where(User.email == email.strip().lower())
    )).scalar_one_or_none()
    if existing is not None:
        raise AuthError("conflict", "email already registered", status=409)
    user = User(
        email=email.strip().lower(),
        display_name=display_name.strip()[:120],
        password_hash=passwords.hash_password(password),
        role=role.value,
    )
    session.add(user)
    await session.flush()
    return user


# ---------------------------------------------------------------- csrf
def csrf_ok(header_value: str | None, session_row: SessionRow) -> bool:
    if not header_value or not session_row.csrf_token:
        return False
    return hmac.compare_digest(header_value, session_row.csrf_token)
