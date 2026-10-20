"""Owner scoped camera event listing."""

from __future__ import annotations

import json
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import authenticated_user, get_pagination
from ..models import CameraEvent, Device, User
from ..rbac import EVENT_READ, has_permission
from ..schemas import EventOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=List[EventOut])
def list_owner_events(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> List[EventOut]:
    """List the events of every camera owned by the caller."""
    if not has_permission(user.role, EVENT_READ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")
    limit, offset = get_pagination(limit, offset)
    rows = db.execute(
        select(CameraEvent, Device.name)
        .join(Device, Device.id == CameraEvent.device_id)
        .where(CameraEvent.owner_id == user.id)
        .order_by(CameraEvent.occurred_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    results = []
    for event, device_name in rows:
        try:
            metadata = json.loads(event.metadata_json or "{}")
        except ValueError:  # pragma: no cover - defensive
            metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        results.append(
            EventOut(
                id=event.id,
                device_id=event.device_id,
                device_name=device_name,
                kind=event.kind,
                summary=event.summary,
                confidence=event.confidence,
                occurred_at=event.occurred_at,
                metadata=metadata,
            )
        )
    return results
