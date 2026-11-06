"""FastAPI dependencies: request-scoped DB session + auth/CSRF/RBAC guards.

``get_db_gen`` is FastAPI-cached per request: every dependency that asks for
it shares one ``AsyncSession`` for the whole request lifecycle.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings
from .db import get_session_factory
from .models.session import Session as SessionRow
from .models.user import Role, User
from .services import auth_service


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


async def get_db_gen() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        yield session

DbDep = Annotated[AsyncSession, Depends(get_db_gen)]


async def current_user(
    request: Request,
    db: DbDep,
) -> tuple[User, SessionRow] | None:
    """Resolve the session cookie to a live (user, session) pair."""
    token = request.cookies.get(request.app.state.settings.cookie_session_name, "")
    if not token:
        return None
    result = await auth_service.get_valid_session(db, request.app.state.settings,
                                                  token)
    # commit the last_seen touch immediately (touch happens even on GET)
    await db.commit()
    if result is None:
        return None
    user, row, _secret = result
    return user, row


async def require_user(
    user_pair: Annotated[tuple[User, SessionRow] | None, Depends(current_user)],
) -> tuple[User, SessionRow]:
    if user_pair is None:
        raise auth_service.AuthError("unauthorized", "authentication required",
                                     status=401)
    return user_pair


async def require_csrf(
    request: Request,
    pair: Annotated[tuple[User, SessionRow], Depends(require_user)],
) -> tuple[User, SessionRow]:
    """Mutating endpoints: header X-CSRF-Token must match the session token."""
    user, row = pair
    if not auth_service.csrf_ok(request.headers.get("x-csrf-token"), row):
        raise auth_service.AuthError("csrf_missing",
                                     "missing or invalid CSRF token", status=403)
    return pair


async def require_owner(
    user_pair: Annotated[tuple[User, SessionRow] | None, Depends(current_user)],
) -> tuple[User, SessionRow]:
    if user_pair is None:
        raise auth_service.AuthError("unauthorized", "authentication required",
                                     status=401)
    user, row = user_pair
    if not Role(user.role).at_least(Role.OWNER):
        raise auth_service.AuthError("forbidden", "owner role required", status=403)
    return user, row


async def require_owner_csrf(
    pair: Annotated[tuple[User, SessionRow], Depends(require_csrf)],
) -> tuple[User, SessionRow]:
    """Mutating, owner-only endpoints: CSRF + owner role."""
    user, row = pair
    if not Role(user.role).at_least(Role.OWNER):
        raise auth_service.AuthError("forbidden", "owner role required", status=403)
    return pair
