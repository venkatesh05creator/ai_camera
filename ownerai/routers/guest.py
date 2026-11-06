"""Time-boxed guest access endpoints (Phase 3 item #7).

Ships behind the ``GUEST_ACCESS`` feature flag.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import authenticated_user
from ..features import is_enabled
from ..models import EnrolledIdentity, GuestAccess, User
from ..services.guest import (
    GuestAccessError,
    grant_guest_access,
    is_guest_access_valid,
    list_guest_access,
    revoke_guest_access,
)
from ..settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/guest-access", tags=["guest access"])


def _require_guest_access() -> None:
    if not is_enabled("GUEST_ACCESS"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="GUEST_ACCESS feature is not enabled (set OWNERAI_FEATURE_GUEST_ACCESS=1)",
        )


@router.post("")
def create_guest_access(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, Any]:
    """Grant temporary access to an enrolled identity.

    Body: ``{"enrolled_identity_id": 1, "guest_label": "cleaner", "ttl_hours": 24}``
    """
    _require_guest_access()
    identity_id = int(payload.get("enrolled_identity_id", 0))
    guest_label = str(payload.get("guest_label", "")).strip()[:120]
    ttl_hours = payload.get("ttl_hours")
    ttl = int(ttl_hours) if ttl_hours is not None else None
    if identity_id <= 0 or not guest_label:
        raise HTTPException(status_code=422, detail="enrolled_identity_id and guest_label required")

    try:
        grant = grant_guest_access(user.id, identity_id, guest_label, ttl)
    except GuestAccessError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": grant.id,
        "guest_label": grant.guest_label,
        "enrolled_identity_id": grant.enrolled_identity_id,
        "expires_at": grant.expires_at.isoformat(),
    }


@router.get("")
def list_grants(
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, Any]:
    """List the owner's guest grants."""
    _require_guest_access()
    grants = list_guest_access(user.id)
    return {"feature": "GUEST_ACCESS", "grants": grants}


@router.get("/valid/{enrolled_identity_id}")
def check_valid(
    enrolled_identity_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, Any]:
    """Check whether an enrolled identity currently has valid guest access."""
    _require_guest_access()
    identity = db.get(EnrolledIdentity, enrolled_identity_id)
    if identity is None or identity.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="identity not found")
    valid = is_guest_access_valid(enrolled_identity_id)
    return {"feature": "GUEST_ACCESS", "enrolled_identity_id": enrolled_identity_id, "valid": valid}


@router.post("/{grant_id}/revoke")
def revoke(
    grant_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, Any]:
    """Revoke a guest grant."""
    _require_guest_access()
    ok = revoke_guest_access(grant_id, user.id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="grant not found")
    return {"feature": "GUEST_ACCESS", "revoked": True}
