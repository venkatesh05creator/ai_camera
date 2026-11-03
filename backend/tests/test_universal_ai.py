"""Comprehensive test suite for Universal AI Platform: Global Intelligence & Asset Tracking."""

from __future__ import annotations

import json
from unittest.mock import patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.database import Base
from backend.app.models.entities import (
    Asset,
    GlobalFeedEvent,
    MonitoringRule,
    SavedLocation,
    User,
    Camera,
)
from backend.app.services.asset_tracking_service import (
    correlate_event_with_assets,
    delete_asset,
    get_asset_by_id,
    get_asset_summary,
    get_user_assets,
    register_asset,
    update_asset,
)
from backend.app.services.global_intel_service import (
    get_earthquake_feed,
    get_currency_forex_rates,
    get_live_traffic_intelligence,
    get_near_earth_objects,
    get_public_cameras,
    get_unified_map_markers,
    get_weather_intelligence,
)
from backend.app.services.ai_orchestrator import (
    AIIntent,
    AIOrchestrator,
    AIRequestContext,
    IntentClassifier,
)


@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    user = User(
        id="usr_test_universal",
        email="owner@universal.ai",
        password_hash="argon2id_hash_placeholder",
        display_name="Universal Commander",
        role="owner",
        status="active",
    )
    cam = Camera(
        id="cam_garage",
        name="Garage Entrance Camera",
        location_label="Garage Bay 1",
        owner_user_id=user.id,
    )
    session.add(user)
    session.add(cam)
    session.commit()

    yield session
    session.close()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Database Entity Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_universal_ai_entity_persistence(in_memory_db):
    """Verify Asset, GlobalFeedEvent, MonitoringRule, and SavedLocation persist correctly."""
    # 1. Asset
    asset = Asset(
        id="asset_tesla",
        owner_user_id="usr_test_universal",
        name="Tesla Model Y",
        category="vehicle",
        tracking_method="plate",
        identifier="KA-01-MJ-9999",
        status="stationary",
        location_label="Home Garage",
    )
    in_memory_db.add(asset)

    # 2. GlobalFeedEvent
    quake = GlobalFeedEvent(
        domain="disaster",
        event_type="earthquake",
        title="M 6.2 - Northern Chile",
        severity="high",
        latitude=-23.45,
        longitude=-69.12,
        source_name="USGS",
    )
    in_memory_db.add(quake)

    # 3. MonitoringRule
    rule = MonitoringRule(
        owner_user_id="usr_test_universal",
        rule_name="Nighttime Vehicle Movement",
        domain="camera",
        condition_type="presence",
        schedule="22:00-06:00",
    )
    in_memory_db.add(rule)

    # 4. SavedLocation
    loc = SavedLocation(
        owner_user_id="usr_test_universal",
        label="Headquarters Facility",
        latitude=12.9716,
        longitude=77.5946,
        radius_km=15.0,
    )
    in_memory_db.add(loc)
    in_memory_db.commit()

    # Query back
    saved_asset = in_memory_db.query(Asset).filter_by(id="asset_tesla").first()
    assert saved_asset is not None
    assert saved_asset.name == "Tesla Model Y"
    assert saved_asset.identifier == "KA-01-MJ-9999"

    saved_quake = in_memory_db.query(GlobalFeedEvent).filter_by(event_type="earthquake").first()
    assert saved_quake is not None
    assert saved_quake.severity == "high"

    saved_rule = in_memory_db.query(MonitoringRule).filter_by(rule_name="Nighttime Vehicle Movement").first()
    assert saved_rule is not None
    assert saved_rule.schedule == "22:00-06:00"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Asset Tracking Service Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_asset_crud_lifecycle(in_memory_db):
    """Test full CRUD operations on personal asset registry."""
    user_id = "usr_test_universal"

    # Register
    asset = register_asset(
        db=in_memory_db,
        owner_user_id=user_id,
        name="Developer ThinkPad X1",
        category="equipment",
        tracking_method="visual",
        identifier="SN-X1-9876",
        location_label="Workstation 1",
    )
    assert asset.id is not None
    assert asset.status == "stationary"

    # Read
    assets = get_user_assets(in_memory_db, user_id)
    assert len(assets) == 1
    assert assets[0].name == "Developer ThinkPad X1"

    # Summary
    summary = get_asset_summary(in_memory_db, user_id)
    assert summary["total_assets"] == 1
    assert summary["by_category"].get("equipment") == 1

    # Update
    updated = update_asset(in_memory_db, user_id, asset.id, location_label="Meeting Room B", status="active")
    assert updated.location_label == "Meeting Room B"
    assert updated.status == "active"

    # Delete
    del_ok = delete_asset(in_memory_db, user_id, asset.id)
    assert del_ok is True
    assert len(get_user_assets(in_memory_db, user_id)) == 0


def test_asset_correlation_with_camera_events(in_memory_db):
    """Test matching incoming camera OCR and visual detections with registered assets."""
    user_id = "usr_test_universal"

    # Register vehicle and equipment
    car = register_asset(
        db=in_memory_db,
        owner_user_id=user_id,
        name="Family SUV",
        category="vehicle",
        tracking_method="plate",
        identifier="DL-08-CC-1234",
        location_label="Driveway",
    )
    laptop = register_asset(
        db=in_memory_db,
        owner_user_id=user_id,
        name="MacBook Pro",
        category="equipment",
        tracking_method="visual",
        location_label="Desk",
    )

    # Simulate camera detecting car with OCR matching the plate
    matches = correlate_event_with_assets(
        db=in_memory_db,
        owner_user_id=user_id,
        camera_id="cam_garage",
        detected_classes=["car"],
        ocr_texts=["DL08CC1234", "SPEED LIMIT 20"],
        location_label="Garage Bay 1",
    )
    assert len(matches) >= 1
    assert matches[0]["asset_name"] == "Family SUV"
    assert "Plate/Text match" in matches[0]["match_reason"]

    # Verify car status updated in DB
    reloaded_car = get_asset_by_id(in_memory_db, user_id, car.id)
    assert reloaded_car.status == "active"
    assert reloaded_car.location_label == "Garage Bay 1"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Global Intelligence Source Adapters Tests (Mocked for Zero-Network Flake)
# ─────────────────────────────────────────────────────────────────────────────

def test_earthquake_adapter_parsing():
    """Verify USGS GeoJSON response parsing and magnitude classification."""
    mock_usgs = {
        "features": [
            {
                "id": "us7000test",
                "properties": {
                    "mag": 6.8,
                    "place": "12 km SW of Valparaiso, Chile",
                    "time": 1700000000000,
                    "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000test",
                    "tsunami": 1,
                },
                "geometry": {
                    "coordinates": [-71.62, -33.04, 35.0]
                }
            }
        ]
    }

    with patch("backend.app.services.global_intel_service._http_get_json", return_value=mock_usgs):
        quakes = get_earthquake_feed(min_magnitude=3.0, limit=5)
        assert len(quakes) == 1
        q = quakes[0]
        assert q["magnitude"] == 6.8
        assert q["severity"] == "critical"
        assert q["tsunami_alert"] is True
        assert q["latitude"] == -33.04
        assert q["longitude"] == -71.62


def test_weather_adapter_parsing():
    """Verify Open-Meteo REST response parsing."""
    mock_weather = {
        "current": {
            "temperature_2m": 24.5,
            "apparent_temperature": 25.1,
            "relative_humidity_2m": 60,
            "precipitation": 0.0,
            "weather_code": 1,
            "wind_speed_10m": 12.0,
            "surface_pressure": 1012.5,
        },
        "daily": {
            "time": ["2026-11-01", "2026-11-02"],
            "temperature_2m_max": [27.0, 26.5],
            "temperature_2m_min": [18.0, 17.5],
            "weather_code": [1, 2],
        }
    }

    with patch("backend.app.services.global_intel_service._http_get_json", return_value=mock_weather):
        w = get_weather_intelligence(28.6139, 77.2090, "New Delhi")
        assert w["temperature_c"] == 24.5
        assert w["condition"] == "Mainly clear"
        assert len(w["daily_forecast"]) == 2


def test_traffic_intelligence_parsing():
    """Verify verified traffic feed extraction and corridor delay metrics."""
    traffic = get_live_traffic_intelligence(limit=5)
    assert len(traffic) > 0
    tf = traffic[0]
    assert "corridor" in tf
    assert "flow_speed_mph" in tf
    assert "delay_minutes" in tf
    assert tf["status"] in ["normal_flow", "moderate_congestion", "heavy_traffic"]


def test_space_asteroids_parsing():
    """Verify NASA NeoWs Near Earth Objects parsing."""
    mock_nasa = {
        "near_earth_objects": {
            "2026-11-01": [
                {
                    "id": "2026TX",
                    "name": "Asteroid 2026 TX",
                    "estimated_diameter": {
                        "meters": {"estimated_diameter_min": 45.2, "estimated_diameter_max": 101.5}
                    },
                    "is_potentially_hazardous_asteroid": False,
                    "close_approach_data": [
                        {
                            "miss_distance": {"kilometers": "4500000"},
                            "relative_velocity": {"kilometers_per_hour": "54000"},
                            "close_approach_date_full": "2026-Nov-01 14:30",
                        }
                    ],
                }
            ]
        }
    }

    with patch("backend.app.services.global_intel_service._http_get_json", return_value=mock_nasa):
        asteroids = get_near_earth_objects(limit=5)
        assert len(asteroids) == 1
        ast = asteroids[0]
        assert ast["name"] == "Asteroid 2026 TX"
        assert ast["is_hazardous"] is False
        assert ast["miss_distance_km"] == 4500000


def test_public_cameras_catalog():
    """Verify open municipal camera catalog availability."""
    cams = get_public_cameras()
    assert len(cams) >= 4
    cam_names = [c["name"] for c in cams]
    assert any("Times Square" in name for name in cam_names)
    assert any("Shibuya" in name for name in cam_names)


def test_unified_map_markers_aggregation():
    """Verify aggregation of earthquakes, public cameras, and traffic feeds into unified GeoJSON markers."""
    with patch("backend.app.services.global_intel_service.get_earthquake_feed", return_value=[
        {"id": "eq1", "title": "M 5.1 Quake", "depth_km": 10.0, "magnitude": 5.1, "latitude": 37.77, "longitude": -122.41, "severity": "high", "source_name": "USGS", "occurred_at": "2026-11-01T12:00:00Z"}
    ]):
        with patch("backend.app.services.global_intel_service.get_live_traffic_intelligence", return_value=[
            {"id": "tf1", "title": "FDR Drive & 42nd St", "corridor": "FDR Northbound", "flow_speed_mph": 40, "status": "normal_flow", "latitude": 40.74, "longitude": -73.96, "source_name": "NYC DOT", "source_url": ""}
        ]):
            markers = get_unified_map_markers()
            layers = {m["layer"] for m in markers}
            assert "disaster" in layers
            assert "camera" in layers
            assert "traffic" in layers
            assert "security" in layers


# ─────────────────────────────────────────────────────────────────────────────
# 4. Universal AI Orchestrator Intent Routing & Execution
# ─────────────────────────────────────────────────────────────────────────────

def test_intent_classification_for_global_intel_and_asset_tracking():
    """Verify natural language queries route to GLOBAL_INTELLIGENCE and ASSET_TRACKING."""
    # Global Intelligence queries
    queries_global = [
        "Are there any major earthquakes today?",
        "Check global natural disasters",
        "Check roadway traffic conditions",
        "What asteroids are approaching Earth?",
        "Show me public traffic cameras",
        "Check live forex rates and currencies",
    ]
    for q in queries_global:
        intent, conf, _, _ = IntentClassifier.classify(q)
        assert intent == AIIntent.GLOBAL_INTELLIGENCE, f"Failed on query: {q} (got {intent})"

    # Asset tracking queries
    queries_assets = [
        "Where is my registered car?",
        "Track my vehicle",
        "Locate my laptop",
        "List all my registered assets",
        "Find my car in the camera history",
    ]
    for q in queries_assets:
        intent, conf, _, _ = IntentClassifier.classify(q)
        assert intent == AIIntent.ASSET_TRACKING, f"Failed on query: {q} (got {intent})"


def test_ai_orchestrator_execution_global_intelligence():
    """Verify AIOrchestrator generates evidence-based answer and speech for global intelligence."""
    res = AIOrchestrator.process_request(query="Are there any recent earthquakes?")

    assert res.execution_status == "success"
    assert "USGS" in res.answer or "Disaster" in res.answer or "seismic" in res.answer
    assert len(res.speech_text) > 0


def test_ai_orchestrator_execution_asset_tracking(in_memory_db):
    """Verify AIOrchestrator generates asset tracking response."""
    # Seed an asset
    register_asset(
        db=in_memory_db,
        owner_user_id="default",
        name="Company Van",
        category="vehicle",
        location_label="Parking Bay 4",
    )

    res = AIOrchestrator.process_request(
        query="Where is my registered car?",
        user_id="default",
        db=in_memory_db,
    )

    assert res.execution_status == "success"
    assert "Asset" in res.answer or "Company Van" in res.answer
    assert len(res.speech_text) > 0


# ─────────────────────────────────────────────────────────────────────────────
# 5. Computer Control, Screen Understanding & Proactive Intelligence
# ─────────────────────────────────────────────────────────────────────────────

def test_computer_control_service_and_approval_gate():
    """Verify ComputerControlService safe file search, read, write gating, and diagnostics."""
    from backend.app.services.computer_control_service import ComputerControlService

    # 1. File search
    res = ComputerControlService.search_workspace_files("requirements.json")
    assert res.get("success") is True
    assert res["count"] >= 1
    assert any("requirements.json" in r["name"] for r in res["results"])

    # 2. Document read
    doc = ComputerControlService.read_document("engineering/requirements.json", max_lines=10)
    assert doc.get("success") is True
    assert "Universal Jarvis AI Command Center" in doc["content"]

    # 3. Path traversal protection
    traversal = ComputerControlService.read_document("../../Windows/System32/drivers/etc/hosts")
    assert "error" in traversal

    # 4. Sensitive write approval gating
    write_res = ComputerControlService.write_document(
        relative_path="engineering/requirements.json",
        content="{\"test\": 1}",
        overwrite=True,
        approved=False,
    )
    assert write_res["status"] == "requires_approval"
    action_id = write_res["action_id"]

    # 5. Verify pending list
    pending = ComputerControlService.list_pending_approvals()
    assert any(p["action_id"] == action_id for p in pending)

    # 6. Reject pending action
    reject_res = ComputerControlService.resolve_approval(action_id, approved=False)
    assert reject_res["status"] == "rejected"

    # 7. Host diagnostics
    diag = ComputerControlService.inspect_system_diagnostics()
    assert diag["status"] == "healthy"
    assert "cpu_percent" in diag
    assert "memory" in diag
    assert "disk" in diag


def test_screen_understanding_service_consent_and_analysis():
    """Verify ScreenUnderstandingService requires consent and analyzes screen geometry."""
    import base64
    from backend.app.services.screen_understanding_service import ScreenUnderstandingService

    import cv2
    import numpy as np
    arr = np.zeros((1080, 1920, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".png", arr)
    b64_str = base64.b64encode(buf.tobytes() if hasattr(buf, "tobytes") else bytes(buf)).decode("utf-8")

    # 1. Consent required
    no_consent = ScreenUnderstandingService.analyze_screen_frame(b64_str, explicit_consent=False)
    assert no_consent.get("status") == "consent_required"

    # 2. Successful analysis with consent
    analysis = ScreenUnderstandingService.analyze_screen_frame(
        image_base64=b64_str,
        user_query="Inspect screen for errors",
        explicit_consent=True,
    )
    assert analysis["status"] == "success"
    assert analysis["screen_geometry"]["width"] == 1920
    assert analysis["screen_geometry"]["height"] == 1080
    assert analysis["screen_geometry"]["aspect_ratio"] == 1.78
    assert "recommendations" in analysis


def test_proactive_intel_notifications_lifecycle():
    """Verify ProactiveIntelService condition evaluation, deduplication, and snooze/dismiss."""
    from backend.app.services.proactive_intel_service import ProactiveIntelService

    # 1. Trigger camera offline alert
    dispatched = ProactiveIntelService.evaluate_system_conditions(
        active_cameras_count=0,
        system_cpu_percent=10.0,
        unacknowledged_alerts_count=0,
    )
    assert len(dispatched) >= 1
    assert any(n["category"] == "camera" for n in dispatched)

    # 2. Deduplication prevents immediate re-trigger
    dup = ProactiveIntelService.evaluate_system_conditions(
        active_cameras_count=0,
        system_cpu_percent=10.0,
        unacknowledged_alerts_count=0,
    )
    assert len(dup) == 0

    # 3. Retrieve notifications list
    notifs = ProactiveIntelService.get_notifications()
    assert len(notifs) >= 1
    first_id = notifs[0]["id"]

    # 4. Acknowledge notification
    ack = ProactiveIntelService.acknowledge_notification(first_id)
    assert ack is True

    # 5. Dismiss notification
    dismiss = ProactiveIntelService.dismiss_notification(first_id)
    assert dismiss is True


