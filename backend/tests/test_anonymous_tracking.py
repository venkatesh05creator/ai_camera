"""Integration tests for anonymous tracking and detection events."""

from fastapi import status
from backend.app.models.entities import Camera, DetectionEvent


def test_anonymous_tracking_event_storage(client, admin_headers, db_session, test_admin_user):
    # Setup test camera
    cam = Camera(name="Corridor Cam", source_type="webcam", location_label="Hallway", status="online", owner_user_id=test_admin_user.id)
    db_session.add(cam)
    db_session.commit()
    db_session.refresh(cam)

    # 1. Record an unidentified detection event
    event = DetectionEvent(
        camera_id=cam.id,
        event_type="person_detected",
        track_id="TRK-1082",
        person_id=None,  # Unknown person MUST have NULL person_id - never a fabricated profile!
        confidence=0.88,
        review_status="unreviewed",
        metadata_json='{"motion_score": 0.45, "anonymous": true}',
    )
    db_session.add(event)
    db_session.commit()

    # 2. Query events via API
    response = client.get(f"/api/v1/events?camera_id={cam.id}", headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) >= 1
    ev = next(e for e in data if e["track_id"] == "TRK-1082")
    assert ev["person_id"] is None
    assert ev["track_id"] == "TRK-1082"
    assert ev["event_type"] == "person_detected"
    assert ev["person_name"] is None or ev["person_name"] == ""


def test_event_review_action(client, admin_headers, db_session):
    cam = db_session.query(Camera).first()
    event = DetectionEvent(
        camera_id=cam.id,
        event_type="person_detected",
        track_id="TRK-9901",
        person_id=None,
        confidence=0.75,
        review_status="unreviewed",
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    # Review event via PUT
    resp_rev = client.put(
        f"/api/v1/events/{event.id}/review",
        json={"review_status": "confirmed", "notes": "Verified guest entry"},
        headers=admin_headers,
    )
    assert resp_rev.status_code == status.HTTP_200_OK
    assert resp_rev.json()["review_status"] == "confirmed"
