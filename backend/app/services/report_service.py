"""Reporting and analytics aggregation service."""

from __future__ import annotations

from typing import Any, Dict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.entities import Alert, Camera, DetectionEvent, Person


def generate_summary_report(db: Session) -> Dict[str, Any]:
    """Calculate aggregated metrics and performance stats."""
    total_events = db.scalar(select(func.count(DetectionEvent.id))) or 0
    total_persons = db.scalar(select(func.count(DetectionEvent.id)).where(DetectionEvent.event_type == "person")) or 0
    total_verified = db.scalar(select(func.count(DetectionEvent.id)).where(DetectionEvent.person_id.is_not(None))) or 0
    total_motion = db.scalar(select(func.count(DetectionEvent.id)).where(DetectionEvent.event_type == "motion")) or 0

    active_cameras = db.scalar(select(func.count(Camera.id)).where(Camera.status == "online")) or 0
    enrolled_profiles = db.scalar(select(func.count(Person.id)).where(Person.status == "enrolled")) or 0

    # Events by camera
    events_by_camera: Dict[str, int] = {}
    camera_stmt = (
        select(Camera.name, func.count(DetectionEvent.id))
        .join(DetectionEvent, DetectionEvent.camera_id == Camera.id)
        .group_by(Camera.name)
    )
    for cam_name, count in db.execute(camera_stmt).all():
        events_by_camera[cam_name] = int(count)

    # Events by type
    events_by_type: Dict[str, int] = {}
    type_stmt = (
        select(DetectionEvent.event_type, func.count(DetectionEvent.id))
        .group_by(DetectionEvent.event_type)
    )
    for etype, count in db.execute(type_stmt).all():
        events_by_type[etype] = int(count)

    # Average alert response time
    resolved_alerts = db.scalars(
        select(Alert).where(Alert.status == "resolved", Alert.resolved_at.is_not(None))
    ).all()
    avg_response = 0.0
    if resolved_alerts:
        diffs = [(a.resolved_at - a.created_at).total_seconds() for a in resolved_alerts if a.resolved_at]
        avg_response = sum(diffs) / len(diffs) if diffs else 0.0

    return {
        "total_events": total_events,
        "total_persons_detected": total_persons,
        "total_verified_matches": total_verified,
        "total_motion_events": total_motion,
        "active_cameras_count": active_cameras,
        "total_enrolled_profiles": enrolled_profiles,
        "events_by_camera": events_by_camera,
        "events_by_type": events_by_type,
        "avg_alert_response_seconds": round(avg_response, 1),
    }
