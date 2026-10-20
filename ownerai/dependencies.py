"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .rbac import has_permission
from .sessions import current_session_from_request, current_user_from_request, validate_csrf
from .settings import get_settings

#: Endpoints that authenticate with a single-use secret in the request body.
CSRF_EXEMPT_PATHS = frozenset(
    {
        "/api/auth/password/reset",
        "/api/auth/email/verify",
    }
)


def optional_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Return the authenticated user or ``None``."""
    return current_user_from_request(request, db)


def authenticated_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Return the authenticated user or raise ``401``."""
    user = current_user_from_request(request, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    return user


async def enforce_csrf(request: Request, db: Session = Depends(get_db)) -> None:
    """Validate the CSRF token of a state-changing request.

    Authenticated requests must echo the session bound token, anonymous
    requests a token signed by the server.

    A small number of endpoints are exempt: they authenticate the request with
    a single-use secret that is carried in the body (a password reset or an
    e-mail confirmation token).  A cross-site attacker cannot know that
    secret, so a forged request can never succeed - and requiring the cookie
    token would lock out the legitimate owner whose session was just revoked.
    """
    if request.url.path in CSRF_EXEMPT_PATHS:
        return
    session = current_session_from_request(request, db)
    await validate_csrf(request, db, session)


def require_permission(permission: str):
    """Return a dependency enforcing a permission for the current user."""

    def dependency(request: Request, db: Session = Depends(get_db)) -> User:
        user = current_user_from_request(request, db)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
        if not has_permission(user.role, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")
        return user

    return dependency


def get_pagination(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> tuple[int, int]:
    """Clamp pagination parameters to the configured maximum."""
    settings = get_settings()
    safe_limit = max(1, min(int(limit), settings.max_page_size))
    safe_offset = max(0, int(offset))
    return safe_limit, safe_offset
