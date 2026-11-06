"""Time-boxed guest access (Phase 3 item #7).

Temporary enrolment that expires automatically.  Links a guest-facing label
to an enrolled identity with an expiry; verification against an expired grant
always returns \"not matched\".  Ships behind the ``GUEST_ACCESS`` feature flag.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ..db import session_scope
from ..features import is_enabled
from ..models import EnrolledIdentity, GuestAccess, User
from ..settings import Settings, get_settings

logger = logging.getLogger(__name__)


class GuestAccessError(RuntimeError):
    """Raised when a guest-access operation fails."""


def grant_guest_access(
    owner_id: int,
    enrolled_identity_id: int,
    guest_label: str,
    ttl_hours: Optional[int] = None,
    *,
    settings: Optional[Settings] = None,
) -> GuestAccess:
    """Create a time-boxed guest grant linked to an enrolled identity."""
    if not is_enabled("GUEST_ACCESS"):
        raise GuestAccessError("GUEST_ACCESS feature is not enabled")
    settings = settings or get_settings()
    ttl = ttl_hours or settings.guest_access_default_ttl_hours
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl)

    with session_scope(settings) as db:
        identity = db.get(EnrolledIdentity, enrolled_identity_id)
        if identity is None or identity.owner_id != owner_id:
            raise GuestAccessError("identity not found")
        if identity.withdrawn_at is not None:
            raise GuestAccessError("identity has been withdrawn")

        grant = GuestAccess(
            owner_id=owner_id,
            enrolled_identity_id=enrolled_identity_id,
            guest_label=guest_label,
            expires_at=expires_at,
        )
        db.add(grant)
        db.commit()
        db.refresh(grant)
        return grant


def is_guest_access_valid(
    enrolled_identity_id: int,
    *,
    settings: Optional[Settings] = None,
) -> bool:
    """Return True if the identity has a valid (unexpired, unrevoked) guest grant."""
    if not is_enabled("GUEST_ACCESS"):
        return False
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    with session_scope(settings) as db:
        grant = (
            db.query(GuestAccess)
            .filter_by(enrolled_identity_id=enrolled_identity_id)
            .filter(GuestAccess.revoked_at.is_(None))
            .order_by(GuestAccess.expires_at.desc())
            .first()
        )
        if grant is None:
            return False
        if grant.expires_at.tzinfo is None:
            grant.expires_at = grant.expires_at.replace(tzinfo=timezone.utc)
        return grant.expires_at > now


def revoke_guest_access(
    grant_id: int,
    owner_id: int,
    *,
    settings: Optional[Settings] = None,
) -> bool:
    """Revoke a guest grant.  Returns False if not found/not owned."""
    if not is_enabled("GUEST_ACCESS"):
        return False
    settings = settings or get_settings()
    with session_scope(settings) as db:
        grant = db.get(GuestAccess, grant_id)
        if grant is None or grant.owner_id != owner_id:
            return False
        grant.revoked_at = datetime.now(timezone.utc)
        db.commit()
        return True


def list_guest_access(
    owner_id: int,
    *,
    settings: Optional[Settings] = None,
) -> list[dict]:
    """List all guest grants for an owner, with validity status."""
    if not is_enabled("GUEST_ACCESS"):
        return []
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    with session_scope(settings) as db:
        rows = db.query(GuestAccess).filter_by(owner_id=owner_id).all()
    result = []
    for grant in rows:
        expired = False
        if grant.expires_at.tzinfo is None:
            grant.expires_at = grant.expires_at.replace(tzinfo=timezone.utc)
        if grant.revoked_at is not None or grant.expires_at <= now:
            expired = True
        result.append(
            {
                "id": grant.id,
                "guest_label": grant.guest_label,
                "enrolled_identity_id": grant.enrolled_identity_id,
                "expires_at": grant.expires_at.isoformat(),
                "revoked_at": grant.revoked_at.isoformat() if grant.revoked_at else None,
                "expired": expired,
            }
        )
    return result
