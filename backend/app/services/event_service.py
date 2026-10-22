"""Detection event pipeline and alert dispatch service."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..models.entities import Alert, DetectionEvent, Person


def record_detection_event(
    db: Session,
    camera_id: str,
    event_type: str,
    track_id: Optional[str] = None,
    person_id: Optional[str] = None,
    confidence: float = 0.0,
    snapshot_key: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    create_alert: bool = True,
    severity: str = "medium",
) -> DetectionEvent:
    """Record a detection or motion event. Enforces person_id nullable for anonymous tracks."""
    now = datetime.now(timezone.utc)
    metadata_str = json.dumps(metadata or {})

    # Update person's last_seen_at if verified
    if person_id:
        person = db.get(Person, person_id)
        if person:
            if not person.first_seen_at:
                person.first_seen_at = now
            person.last_seen_at = now

    event = DetectionEvent(
        camera_id=camera_id,
        occurred_at=now,
        event_type=event_type,
        track_id=track_id,
        person_id=person_id,
        confidence=confidence,
        snapshot_object_key=snapshot_key,
        metadata_json=metadata_str,
    )
    db.add(event)
    db.flush()

    # Trigger alert if requested
    if create_alert:
        title = f"{event_type.replace('_', ' ').capitalize()} Event Detected"
        if person_id:
            title = "Authorized Person Verified"
        elif track_id:
            title = f"Anonymous Person Detected ({track_id})"

        alert = Alert(
            event_id=event.id,
            severity=severity,
            status="active",
            title=title,
            description=f"Observed on camera at {now.strftime('%H:%M:%S UTC')}. Confidence: {confidence*100:.1f}%.",
            created_at=now,
        )
        db.add(alert)

    db.commit()
    db.refresh(event)
    return event


def query_events(
    db: Session,
    camera_id: Optional[str] = None,
    event_type: Optional[str] = None,
    person_id: Optional[str] = None,
    review_status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[DetectionEvent]:
    stmt = select(DetectionEvent).order_by(desc(DetectionEvent.occurred_at))
    if camera_id:
        stmt = stmt.where(DetectionEvent.camera_id == camera_id)
    if event_type:
        stmt = stmt.where(DetectionEvent.event_type == event_type)
    if person_id:
        stmt = stmt.where(DetectionEvent.person_id == person_id)
    if review_status:
        stmt = stmt.where(DetectionEvent.review_status == review_status)

    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


def search_historical_events(
    db: Session,
    query: str,
    camera_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 25,
) -> Dict[str, Any]:
    """Search visual events by natural language intent, timestamp range, and camera ID.
    
    Distinguishes historical findings from live observations with explicit timestamps.
    """
    q_lower = query.lower().strip()
    stmt = select(DetectionEvent).order_by(desc(DetectionEvent.occurred_at))

    if camera_id:
        stmt = stmt.where(DetectionEvent.camera_id == camera_id)
    if start_time:
        stmt = stmt.where(DetectionEvent.occurred_at >= start_time)
    if end_time:
        stmt = stmt.where(DetectionEvent.occurred_at <= end_time)

    # Class / event keyword routing
    if any(k in q_lower for k in ["zone", "enter", "entry"]):
        stmt = stmt.where(DetectionEvent.event_type.in_(["zone_entry", "person", "alert"]))
    elif any(k in q_lower for k in ["exit", "leave", "leaving"]):
        stmt = stmt.where(DetectionEvent.event_type.in_(["zone_exit", "alert"]))
    elif any(k in q_lower for k in ["vehicle", "car", "truck", "bike"]):
        stmt = stmt.where(DetectionEvent.event_type.in_(["vehicle", "motion", "alert"]))
    elif any(k in q_lower for k in ["motion", "movement"]):
        stmt = stmt.where(DetectionEvent.event_type.in_(["motion", "alert"]))
    elif any(k in q_lower for k in ["alert", "unusual", "threat", "breach"]):
        stmt = stmt.where(DetectionEvent.event_type.in_(["alert", "zone_entry", "zone_occupancy_exceeded"]))

    events = list(db.scalars(stmt.limit(limit)).all())
    
    # Assemble natural language summary of findings
    summary = ""
    if not events:
        summary = f"No historical events matching '{query}' were found in the recorded timeline."
    else:
        most_recent = events[0]
        rec_time = most_recent.occurred_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        summary = (
            f"Found {len(events)} historical event(s). Most recent occurrence was recorded at "
            f"{rec_time} (Event Type: {most_recent.event_type}, Confidence: {most_recent.confidence*100:.1f}%)."
        )

    return {
        "query": query,
        "total_results": len(events),
        "summary": summary,
        "is_historical": True,
        "events": events,
    }

