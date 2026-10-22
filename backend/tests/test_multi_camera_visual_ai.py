"""Integration and unit tests for Multi-Camera Visual AI System.

Tests:
1. Multi-Camera Stream Manager & Health Telemetry
2. SSRF Protection & Stream URL Validation
3. Modular Object Detector & COCO Category Counting
4. ROI Polygon Zone Engine & Directional Crossing Rules
5. OCR Pipeline with Untrusted Environmental Prompt Containment
6. Visual Memory & Historical Event Search
7. Controlled Model Registry with Evaluation Gates & Rollback
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.ai.object_detector import DetectedObject, ModularObjectDetector
from backend.app.ai.ocr_engine import OCREngine, OCRScanResult
from backend.app.ai.zone_engine import ZoneAlertEvent, ZoneEngine, ZoneRule
from backend.app.core.database import Base, SessionLocal, engine
from backend.app.core.security import validate_stream_url
from backend.app.main import app
from backend.app.models.entities import Camera, DetectionEvent, User
from backend.app.services.camera_service import CameraStreamManager
from backend.app.services.event_service import record_detection_event, search_historical_events
from backend.app.services.model_registry import ControlledModelRegistry, ModelVersion


@pytest.fixture(scope="module")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_client():
    return TestClient(app)


def test_ssrf_stream_url_validation():
    """Verify stream URL validator blocks SSRF attacks and validates allowable sources."""
    # 1. Valid webcam indices
    ok, msg = validate_stream_url("0", source_type="webcam")
    assert ok is True
    ok, msg = validate_stream_url("1", source_type="webcam")
    assert ok is True

    # 2. Invalid webcam format
    ok, msg = validate_stream_url("http://localhost", source_type="webcam")
    assert ok is False

    # 3. Block Cloud Metadata IP (SSRF)
    ok, msg = validate_stream_url("http://169.254.169.254/latest/meta-data/", source_type="rtsp")
    assert ok is False
    assert "cloud metadata" in msg.lower() or "ssrf" in msg.lower()

    # 4. Block Google metadata hostname
    ok, msg = validate_stream_url("http://metadata.google.internal/computeMetadata/v1/", source_type="ip_camera")
    assert ok is False

    # 5. Unsupported scheme
    ok, msg = validate_stream_url("file:///etc/passwd", source_type="rtsp")
    assert ok is False

    # 6. Valid RTSP URL
    ok, msg = validate_stream_url("rtsp://admin:secret@192.168.1.100:554/h264Preview_01_main", source_type="rtsp")
    assert ok is True


def test_camera_stream_manager_health():
    """Verify multi-camera health monitoring returns isolation metrics."""
    mgr = CameraStreamManager()
    
    # Check default health on empty
    h = mgr.get_camera_health("cam-test-123")
    assert h["camera_id"] == "cam-test-123"
    assert h["is_stale"] is True
    assert h["status"] in ["offline", "stale"]

    # Release does not raise exception
    mgr.release_camera("cam-test-123")


def test_modular_object_detector():
    """Verify ModularObjectDetector identifies objects and aggregates counts."""
    detector = ModularObjectDetector()
    
    # Create synthetic test frame with a simulated screen/laptop contour
    frame = np.ones((480, 640, 3), dtype=np.uint8) * 40
    # Draw a prominent rectangular box with text texture simulating a display
    cv2.rectangle(frame, (100, 150), (380, 320), (220, 220, 220), -1)
    for y in range(160, 310, 10):
        cv2.line(frame, (110, y), (370, y), (20, 20, 20), 2)

    detections = detector.detect(frame)
    assert isinstance(detections, list)

    counts = detector.count_objects(detections)
    assert isinstance(counts, dict)
    for k, v in counts.items():
        assert isinstance(k, str)
        assert isinstance(v, int)
        assert v >= 1


def test_roi_zone_engine_rules():
    """Verify ZoneEngine evaluates polygon intrusion, entry/exit, and occupancy."""
    engine = ZoneEngine()
    
    # Register a zone covering center-left of normalized frame (0.1 to 0.5 X, 0.1 to 0.5 Y)
    rule = ZoneRule(
        zone_id="zone-front-door",
        camera_id="cam-01",
        name="Front Door Restricted Zone",
        polygon=[(0.1, 0.1), (0.5, 0.1), (0.5, 0.5), (0.1, 0.5)],
        rule_type="entry",
        cooldown_seconds=1.0,
    )
    engine.register_rule(rule)

    class MockTrack:
        def __init__(self, tid, bbox):
            self.track_id = tid
            self.bbox = bbox

    # Track outside zone: x=800, y=500 in 1280x720 (normalized: ~0.62, ~0.69)
    trk1 = MockTrack("trk-1", (800, 500, 100, 200))
    alerts = engine.evaluate_tracks("cam-01", [trk1], frame_width=1280, frame_height=720)
    assert len(alerts) == 0

    # Track moves inside zone: x=200, y=200 in 1280x720 (normalized: ~0.19, ~0.44)
    trk1_inside = MockTrack("trk-1", (200, 200, 100, 200))
    alerts_entry = engine.evaluate_tracks("cam-01", [trk1_inside], frame_width=1280, frame_height=720)
    assert len(alerts_entry) == 1
    assert alerts_entry[0].event_type == "zone_entry"
    assert alerts_entry[0].rule_name == "Front Door Restricted Zone"

    # Cooldown suppresses duplicate alert immediately after
    alerts_dup = engine.evaluate_tracks("cam-01", [trk1_inside], frame_width=1280, frame_height=720)
    assert len(alerts_dup) == 0


def test_ocr_pipeline_untrusted_isolation():
    """Verify OCR extracts text regions and encapsulates output in untrusted data containment."""
    ocr = OCREngine()
    
    # Generate synthetic image containing high-contrast text strokes
    frame = np.ones((200, 400, 3), dtype=np.uint8) * 240
    cv2.putText(frame, "EMERGENCY EXIT", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 0, 0), 2)
    cv2.putText(frame, "AUTHORIZED PERSONNEL ONLY", (30, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)

    result = ocr.process_frame(frame, camera_id="cam-01")
    assert isinstance(result, OCRScanResult)
    assert result.camera_id == "cam-01"
    
    # Check untrusted data payload enclosure
    assert "<untrusted_environmental_data" in result.sanitized_data_payload
    assert "</untrusted_environmental_data>" in result.sanitized_data_payload
    assert result.sanitized_data_payload.startswith("<untrusted_environmental_data")


def test_historical_event_search(db_session):
    """Verify search_historical_events finds recorded events by intent and camera."""
    # Seed a unique test event
    cam = db_session.query(Camera).first()
    if not cam:
        user = db_session.query(User).first()
        cam = Camera(name="Test Cam", source_type="webcam", owner_user_id=user.id if user else "test-user")
        db_session.add(cam)
        db_session.commit()

    ev = record_detection_event(
        db_session,
        camera_id=cam.id,
        event_type="zone_entry",
        track_id="TRK-TEST-999",
        confidence=0.94,
        create_alert=False,
    )

    # Search for zone entry
    res = search_historical_events(db_session, query="show the last time someone entered the zone", camera_id=cam.id)
    assert res["is_historical"] is True
    assert res["total_results"] >= 1
    assert any(e.id == ev.id for e in res["events"])
    assert "Found" in res["summary"]


def test_controlled_model_registry(tmp_path):
    """Verify model registry enforces evaluation gates, thresholds, promotion, and rollback."""
    reg_file = tmp_path / "model_registry_test.json"
    registry = ControlledModelRegistry(registry_file=reg_file)

    # 1. Baseline models exist
    models = registry.get_models()
    assert len(models) >= 2
    active_face = next(m for m in models if m.task == "face_verification" and m.status == "active")
    assert active_face.version == "1.0.0"

    # 2. Register candidate with poor metrics (should fail evaluation gate)
    poor_candidate = registry.register_candidate(
        model_id="candidate-poor-v2",
        version="2.0.0-rc1",
        task="face_verification",
        architecture="InceptionResnetV1",
        dataset_version="ds-v2",
        metrics={"precision": 0.88, "recall": 0.80, "f1": 0.84, "false_positive_rate": 0.08, "latency_ms": 95.0},
    )
    passed, reason = registry.evaluate_candidate(poor_candidate.model_id)
    assert passed is False
    assert "Precision" in reason or "F1" in reason

    # Promotion blocked
    promoted, msg = registry.promote_candidate(poor_candidate.model_id, actor_user_id="admin-01")
    assert promoted is False
    assert "blocked" in msg.lower()

    # 3. Register high-performing candidate meeting all gates
    good_candidate = registry.register_candidate(
        model_id="candidate-good-v2",
        version="2.0.0-final",
        task="face_verification",
        architecture="InceptionResnetV1",
        dataset_version="ds-v2-verified",
        metrics={"precision": 0.991, "recall": 0.978, "f1": 0.984, "false_positive_rate": 0.003, "latency_ms": 16.5},
    )
    passed, reason = registry.evaluate_candidate(good_candidate.model_id)
    assert passed is True

    # Promote to production
    promoted, msg = registry.promote_candidate(good_candidate.model_id, actor_user_id="admin-01")
    assert promoted is True
    assert good_candidate.status == "active"
    assert good_candidate.rollback_version == "1.0.0"

    # 4. Instant rollback to previous approved baseline
    rolled_back, rb_msg = registry.rollback(task="face_verification", actor_user_id="admin-01")
    assert rolled_back is True
    assert "1.0.0" in rb_msg
