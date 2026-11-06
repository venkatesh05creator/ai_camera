"""Evidence panel endpoints (Phase 3 item #1).

Every JARVIS answer links to the exact snapshot/event IDs, detector output
and confidence behind it.  Ships behind the ``EVIDENCE_PANEL`` feature flag.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import authenticated_user
from ..features import is_enabled
from ..models import AssistantTurn, CameraEvent, Device, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/evidence", tags=["evidence panel"])


def _require_evidence() -> None:
    if not is_enabled("EVIDENCE_PANEL"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="EVIDENCE_PANEL feature is not enabled (set OWNERAI_FEATURE_EVIDENCE_PANEL=1)",
        )


@router.get("/turns/{turn_id}")
def turn_evidence(
    turn_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, Any]:
    """Return the evidence events behind a specific assistant turn."""
    _require_evidence()
    turn = db.get(AssistantTurn, turn_id)
    if turn is None or turn.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="turn not found")

    try:
        event_ids = json.loads(turn.evidence_event_ids_json or "[]")
    except ValueError:
        event_ids = []
    if not isinstance(event_ids, list):
        event_ids = []

    events = []
    if event_ids:
        rows = db.execute(
            select(CameraEvent, Device.name)
            .join(Device, Device.id == CameraEvent.device_id)
            .where(CameraEvent.id.in_(event_ids))
            .where(CameraEvent.owner_id == user.id)
        ).all()
        for event, device_name in rows:
            try:
                metadata = json.loads(event.metadata_json or "{}")
            except ValueError:
                metadata = {}
            events.append(
                {
                    "id": event.id,
                    "device_id": event.device_id,
                    "device_name": device_name,
                    "kind": event.kind,
                    "summary": event.summary,
                    "confidence": event.confidence,
                    "occurred_at": event.occurred_at.isoformat(),
                    "metadata": metadata,
                }
            )

    return {
        "feature": "EVIDENCE_PANEL",
        "turn_id": turn_id,
        "intent": turn.intent,
        "answer": turn.answer,
        "evidence_events": events,
        "evidence_count": len(events),
    }


@router.get("/latest")
def latest_evidence(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, Any]:
    """Return evidence for the most recent assistant turns."""
    _require_evidence()
    turns = (
        db.query(AssistantTurn)
        .filter_by(owner_id=user.id)
        .order_by(AssistantTurn.created_at.desc())
        .limit(limit)
        .all()
    )
    result = []
    for turn in turns:
        try:
            event_ids = json.loads(turn.evidence_event_ids_json or "[]")
        except ValueError:
            event_ids = []
        result.append(
            {
                "turn_id": turn.id,
                "created_at": turn.created_at.isoformat(),
                "intent": turn.intent,
                "answer": turn.answer,
                "evidence_event_ids": event_ids,
                "evidence_count": len(event_ids),
            }
        )
    return {"feature": "EVIDENCE_PANEL", "turns": result}
