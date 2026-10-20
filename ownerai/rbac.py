"""Role based access control.

Permissions are evaluated on the server for every request.  The UI hides
controls for convenience only - the API never trusts a client supplied role,
owner id or permission flag.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable, Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .db import get_db
from .models import Role, User

logger = logging.getLogger(__name__)

# --- permission catalogue --------------------------------------------------
DEVICE_READ = "devices:read"
DEVICE_WRITE = "devices:write"
DEVICE_DELETE = "devices:delete"
EVENT_READ = "events:read"
EVENT_WRITE = "events:write"
IDENTITY_READ = "identities:read"
IDENTITY_WRITE = "identities:write"
IDENTITY_DELETE = "identities:delete"
CHAT_READ = "chat:read"
CHAT_WRITE = "chat:write"
SEARCH_READ = "search:read"
SETTINGS_READ = "settings:read"
SETTINGS_WRITE = "settings:write"
ADMIN_USERS = "admin:users"
ADMIN_AUDIT = "admin:audit"
ADMIN_ROLES = "admin:roles"
ADMIN_CONTACTS = "admin:contacts"

_VIEWER_PERMISSIONS = frozenset(
    {
        DEVICE_READ,
        EVENT_READ,
        IDENTITY_READ,
        CHAT_READ,
        SEARCH_READ,
        SETTINGS_READ,
    }
)

_TRUSTED_PERMISSIONS = frozenset(
    _VIEWER_PERMISSIONS
    | {
        DEVICE_WRITE,
        EVENT_WRITE,
        IDENTITY_WRITE,
        IDENTITY_DELETE,
        CHAT_WRITE,
        SETTINGS_WRITE,
    }
)

_ADMIN_PERMISSIONS = frozenset(
    _TRUSTED_PERMISSIONS
    | {
        DEVICE_DELETE,
        ADMIN_USERS,
        ADMIN_AUDIT,
        ADMIN_CONTACTS,
    }
)

_OWNER_PERMISSIONS = frozenset(_ADMIN_PERMISSIONS | {ADMIN_ROLES})

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    Role.VIEWER.value: _VIEWER_PERMISSIONS,
    Role.TRUSTED.value: _TRUSTED_PERMISSIONS,
    Role.ADMIN.value: _ADMIN_PERMISSIONS,
    Role.OWNER.value: _OWNER_PERMISSIONS,
}

#: Roles a given actor is allowed to assign to somebody else.
ASSIGNABLE_ROLES: dict[str, frozenset[str]] = {
    Role.OWNER.value: frozenset({Role.OWNER.value, Role.ADMIN.value, Role.TRUSTED.value, Role.VIEWER.value}),
    Role.ADMIN.value: frozenset({Role.ADMIN.value, Role.TRUSTED.value, Role.VIEWER.value}),
    Role.TRUSTED.value: frozenset({Role.VIEWER.value}),
    Role.VIEWER.value: frozenset(),
}


def permissions_for(role: str) -> frozenset[str]:
    """Return the permission set of a role (empty for unknown roles)."""
    return ROLE_PERMISSIONS.get(role, frozenset())


def has_permission(role: str, permission: str) -> bool:
    """Check a single permission for a role."""
    return permission in permissions_for(role)


def is_privileged(role: str) -> bool:
    """Return ``True`` for administrative roles."""
    return role in {Role.ADMIN.value, Role.OWNER.value}


def role_rank(role: str) -> int:
    """Higher rank means more privileges."""
    return {Role.VIEWER.value: 0, Role.TRUSTED.value: 1, Role.ADMIN.value: 2, Role.OWNER.value: 3}.get(role, -1)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
def require_permission(permission: str) -> Callable[..., User]:
    """Build a dependency that resolves the current user and checks a permission."""

    def dependency(request: Request, db: Session = Depends(get_db)) -> User:
        from .sessions import current_user_from_request  # local import to avoid a cycle

        user = current_user_from_request(request, db)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
        if not has_permission(user.role, permission):
            logger.warning(
                "permission denied",
                extra={"permission": permission, "role": user.role, "user_id": user.id},
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")
        return user

    return dependency


def require_any_permission(*permissions: str) -> Callable[..., User]:
    """Build a dependency accepting any one of the supplied permissions."""

    def dependency(request: Request, db: Session = Depends(get_db)) -> User:
        from .sessions import current_user_from_request

        user = current_user_from_request(request, db)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
        if not any(has_permission(user.role, permission) for permission in permissions):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")
        return user

    return dependency


def require_role(*roles: str) -> Callable[..., User]:
    """Build a dependency restricted to the supplied roles."""

    def dependency(request: Request, db: Session = Depends(get_db)) -> User:
        from .sessions import current_user_from_request

        user = current_user_from_request(request, db)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")
        return user

    return dependency


def require_recent_auth(minutes: int = 10) -> Callable[..., User]:
    """Require a fresh authentication (password re-entry) for critical actions."""

    def dependency(request: Request, db: Session = Depends(get_db)) -> User:
        from .sessions import current_session_from_request

        session = current_session_from_request(request, db)
        if session is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
        user = session.user
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
        created = session.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created < datetime.now(timezone.utc) - timedelta(minutes=minutes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="recent authentication required",
            )
        return user

    return dependency


# ---------------------------------------------------------------------------
# Ownership helpers
# ---------------------------------------------------------------------------
def owns_resource(user: User, resource) -> bool:
    """Return ``True`` when ``resource`` belongs to ``user``."""
    owner_id = getattr(resource, "owner_id", None)
    return owner_id is not None and owner_id == user.id


def resource_or_404(db: Session, model, resource_id: int, user: User, *, admin_permission: Optional[str] = None):
    """Fetch a resource, enforcing ownership (or an explicit admin permission).

    Raises ``404`` (not ``403``) for resources owned by somebody else so that
    the API does not disclose the existence of foreign objects.
    """
    obj = db.get(model, resource_id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    if owns_resource(user, obj):
        return obj
    if admin_permission and has_permission(user.role, admin_permission):
        return obj
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")


def assignable_roles_for(actor_role: str) -> frozenset[str]:
    """Roles the given actor may assign."""
    return ASSIGNABLE_ROLES.get(actor_role, frozenset())


def roles_at_or_below(roles: Iterable[str]) -> list[str]:
    """Filter a list of role names, keeping only known ones."""
    known = set(ROLE_PERMISSIONS)
    return [role for role in roles if role in known]
