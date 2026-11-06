"""Privacy zone CRUD endpoints (Phase 3 item #4).

Ships behind the ``PRIVACY_ZONES`` feature flag.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import authenticated_user
from ..features import is_enabled
from ..models import Device, PrivacyZone, User
from ..settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/privacy-zones", tags=["privacy zones"])


def _require_zones() -> None:
    if not is_enabled("PRIVACY_ZONES"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PRIVACY_ZONES feature is not enabled (set OWNERAI_FEATURE_PRIVACY_ZONES=1)",
        )


@router.post("")
def create_privacy_zone(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, Any]:
    """Create an owner-drawn privacy zone.

    Body: ``{"device_id": 1, "name": "...", "polygon": [[x,y], ...]}``
    Coordinates are normalised 0..1.
    """
    _require_zones()
    device_id = int(payload.get("device_id", 0))
    name = str(payload.get("name", "")).strip()[:120]
    polygon = payload.get("polygon")
    if not name or not isinstance(polygon, list) or len(polygon) < 3:
        raise HTTPException(status_code=422, detail="name and polygon (3+ points) required")
    device = db.get(Device, device_id)
    if device is None or device.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device not found")

    zone = PrivacyZone(
        device_id=device_id,
        owner_id=user.id,
        name=name,
        polygon_json=json.dumps(polygon),
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return {
        "id": zone.id,
        "device_id": zone.device_id,
        "name": zone.name,
        "polygon": polygon,
        "created_at": zone.created_at.isoformat(),
    }


@router.get("")
def list_privacy_zones(
    device_id: Optional[int] = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, Any]:
    """List privacy zones, optionally filtered by device."""
    _require_zones()
    query = db.query(PrivacyZone).filter(PrivacyZone.owner_id == user.id)
    if device_id is not None:
        device = db.get(Device, device_id)
        if device is None or device.owner_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device not found")
        query = query.filter(PrivacyZone.device_id == device_id)
    rows = query.all()
    return {
        "feature": "PRIVACY_ZONES",
        "zones": [
            {
                "id": z.id,
                "device_id": z.device_id,
                "name": z.name,
                "polygon": json.loads(z.polygon_json),
                "created_at": z.created_at.isoformat(),
            }
            for z in rows
        ],
    }


@router.delete("/{zone_id}")
def delete_privacy_zone(
    zone_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, bool]:
    """Delete one of the owner's privacy zones."""
    _require_zones()
    zone = db.get(PrivacyZone, zone_id)
    if zone is None or zone.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="zone not found")
    db.delete(zone)
    db.commit()
    return {"ok": True}
