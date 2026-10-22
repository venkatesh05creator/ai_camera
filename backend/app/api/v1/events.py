"""Detection events timeline router."""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...models.entities import Camera, DetectionEvent, Person, User
from ...schemas.schemas import EventOut
from ...services.audit_service import log_action
from ...services.event_service import query_events, search_historical_events
from .auth import get_current_user

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/historical-search")
def search_events(
    q: str = Query(..., description="Natural language search query e.g. 'last time a person entered'"),
    camera_id: Optional[str] = Query(None),
    limit: int = Query(25, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Natural language and filtered historical visual event search."""
    res = search_historical_events(db, query=q, camera_id=camera_id, limit=limit)
    out_events = []
    for ev in res["events"]:
        cam = db.get(Camera, ev.camera_id)
        person = db.get(Person, ev.person_id) if ev.person_id else None
        snap_url = f"/api/v1/stream/snapshot/{ev.snapshot_object_key}" if ev.snapshot_object_key else None
        out_events.append(
            EventOut(
                id=ev.id,
                camera_id=ev.camera_id,
                camera_name=cam.name if cam else "Camera",
                occurred_at=ev.occurred_at,
                event_type=ev.event_type,
                track_id=ev.track_id,
                person_id=ev.person_id,
                person_name=person.name if person else None,
                confidence=ev.confidence,
                snapshot_url=snap_url,
                review_status=ev.review_status,
                metadata_json=ev.metadata_json,
            )
        )
    return {
        "query": res["query"],
        "total_results": res["total_results"],
        "summary": res["summary"],
        "is_historical": True,
        "events": out_events,
    }



@router.get("", response_model=List[EventOut])
def get_events(
    camera_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    person_id: Optional[str] = Query(None),
    review_status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    events = query_events(
        db,
        camera_id=camera_id,
        event_type=event_type,
        person_id=person_id,
        review_status=review_status,
        limit=limit,
        offset=offset,
    )

    out_list = []
    for ev in events:
        cam = db.get(Camera, ev.camera_id)
        person = db.get(Person, ev.person_id) if ev.person_id else None

        snap_url = f"/api/v1/stream/snapshot/{ev.snapshot_object_key}" if ev.snapshot_object_key else None

        out_list.append(
            EventOut(
                id=ev.id,
                camera_id=ev.camera_id,
                camera_name=cam.name if cam else "Camera",
                occurred_at=ev.occurred_at,
                event_type=ev.event_type,
                track_id=ev.track_id,
                person_id=ev.person_id,
                person_name=person.name if person else None,
                confidence=ev.confidence,
                snapshot_url=snap_url,
                review_status=ev.review_status,
                metadata_json=ev.metadata_json,
            )
        )
    return out_list


@router.put("/{event_id}/review")
def review_event(
    event_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = db.get(DetectionEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    new_status = payload.get("review_status", "confirmed")
    if new_status not in ["confirmed", "false_positive", "unreviewed"]:
        raise HTTPException(status_code=422, detail="Invalid review_status")

    event.review_status = new_status
    db.commit()

    log_action(db, action="event.review", resource_type="event", actor_user_id=current_user.id, resource_id=event.id, details={"status": new_status})
    return {"status": "updated", "review_status": new_status}
