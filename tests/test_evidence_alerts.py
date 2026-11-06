"""Tests for evidence panel (Phase 3 #1) and alert rules (Phase 3 #3)."""

from __future__ import annotations

import os

import pytest
from sqlalchemy.orm import Session

from ownerai.db import get_engine
from ownerai.models import AlertRule, AssistantTurn, CameraEvent, Device, User


class TestEvidenceEndpoints:
    def test_evidence_requires_flag(self, owner):
        resp = owner.get("/api/evidence/latest")
        assert resp.status_code == 403

    def test_evidence_turn_not_found(self, owner):
        os.environ["OWNERAI_FEATURE_EVIDENCE_PANEL"] = "1"
        try:
            resp = owner.get("/api/evidence/turns/99999")
            assert resp.status_code == 404
        finally:
            os.environ.pop("OWNERAI_FEATURE_EVIDENCE_PANEL", None)

    def test_evidence_latest(self, owner):
        os.environ["OWNERAI_FEATURE_EVIDENCE_PANEL"] = "1"
        try:
            # Insert a turn directly, capturing ids before the session closes
            with Session(get_engine()) as session:
                user = session.query(User).filter_by(id=1).first()
                user_id = user.id
                turn = AssistantTurn(
                    owner_id=user_id,
                    user_message="who is at the door?",
                    intent="camera_vision_scene",
                    tools_called_json='[]',
                    evidence_event_ids_json='[]',
                    answer="No one at the door.",
                )
                session.add(turn)
                session.commit()
                session.refresh(turn)
                turn_id = turn.id

            resp = owner.get(f"/api/evidence/turns/{turn_id}")
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["turn_id"] == turn_id
            assert data["intent"] == "camera_vision_scene"
            assert data["evidence_count"] == 0
            assert data["evidence_events"] == []

            # With evidence events
            with Session(get_engine()) as session:
                user = session.query(User).filter_by(id=1).first()
                device = Device(owner_id=user.id, name="Cam")
                session.add(device)
                session.commit()
                session.refresh(device)
                event = CameraEvent(
                    device_id=device.id,
                    owner_id=user.id,
                    kind="person",
                    summary="person seen",
                    confidence=0.85,
                    identity_id=None,
                )
                session.add(event)
                session.commit()
                session.refresh(event)
                event_id = event.id

            # Link the event to the turn
            with Session(get_engine()) as session:
                turn = session.query(AssistantTurn).filter_by(id=turn_id).first()
                turn.evidence_event_ids_json = f"[{event_id}]"
                session.commit()

            resp2 = owner.get(f"/api/evidence/turns/{turn_id}")
            assert resp2.status_code == 200
            data2 = resp2.json()
            assert data2["evidence_count"] == 1
            assert data2["evidence_events"][0]["id"] == event_id
            assert data2["evidence_events"][0]["confidence"] == 0.85
        finally:
            os.environ.pop("OWNERAI_FEATURE_EVIDENCE_PANEL", None)


class TestAlertRulesEndpoints:
    def test_create_requires_flag(self, owner):
        resp = owner.post(
            "/api/alert-rules",
            json={"name": "door rule", "nl": "Alert me if someone at the door after 11pm"},
        )
        assert resp.status_code == 403

    def test_create_and_list(self, owner):
        os.environ["OWNERAI_FEATURE_ALERT_RULES"] = "1"
        try:
            # Need a door camera for validation
            with Session(get_engine()) as session:
                user = session.query(User).filter_by(id=1).first()
                device = Device(owner_id=user.id, name="Front Door")
                session.add(device)
                session.commit()

            resp = owner.post(
                "/api/alert-rules",
                json={"name": "door rule", "nl": "Alert me if someone I haven't enrolled is at the door after 11pm"},
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["name"] == "door rule"
            assert data["confirmed_by_owner"] is False
            assert data["enabled"] is False
            assert "parsed" in data
            assert data["parsed"]["condition"] == "unenrolled_person"
            assert data["parsed"]["camera"] == "door"

            # List
            resp2 = owner.get("/api/alert-rules")
            assert resp2.status_code == 200
            data2 = resp2.json()
            assert len(data2["rules"]) == 1
            assert data2["rules"][0]["name"] == "door rule"
        finally:
            os.environ.pop("OWNERAI_FEATURE_ALERT_RULES", None)

    def test_confirm_rule(self, owner):
        os.environ["OWNERAI_FEATURE_ALERT_RULES"] = "1"
        try:
            with Session(get_engine()) as session:
                user = session.query(User).filter_by(id=1).first()
                device = Device(owner_id=user.id, name="Door Cam")
                session.add(device)
                session.commit()
                rule = AlertRule(
                    owner_id=user.id,
                    name="test rule",
                    raw_nl="test",
                    parsed_json='{"condition": "person"}',
                    enabled=False,
                    confirmed_by_owner=False,
                )
                session.add(rule)
                session.commit()
                session.refresh(rule)
                rule_id = rule.id

            resp = owner.post(f"/api/alert-rules/{rule_id}/confirm")
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["confirmed_by_owner"] is True
            assert data["enabled"] is True

            # List should show confirmed
            resp2 = owner.get("/api/alert-rules")
            assert resp2.status_code == 200
            rules = resp2.json()["rules"]
            assert rules[0]["confirmed_by_owner"] is True
            assert rules[0]["enabled"] is True
        finally:
            os.environ.pop("OWNERAI_FEATURE_ALERT_RULES", None)

    def test_rule_referencing_unknown_camera_rejected(self, owner):
        os.environ["OWNERAI_FEATURE_ALERT_RULES"] = "1"
        try:
            resp = owner.post(
                "/api/alert-rules",
                json={"name": "bad rule", "nl": "Alert me if motion at the gate after 9pm"},
            )
            assert resp.status_code == 422, resp.text
        finally:
            os.environ.pop("OWNERAI_FEATURE_ALERT_RULES", None)

    def test_delete_rule(self, owner):
        os.environ["OWNERAI_FEATURE_ALERT_RULES"] = "1"
        try:
            with Session(get_engine()) as session:
                user = session.query(User).filter_by(id=1).first()
                rule = AlertRule(
                    owner_id=user.id,
                    name="to delete",
                    raw_nl="x",
                    parsed_json='{}',
                    enabled=False,
                    confirmed_by_owner=False,
                )
                session.add(rule)
                session.commit()
                session.refresh(rule)
                rule_id = rule.id

            resp = owner.delete(f"/api/alert-rules/{rule_id}")
            assert resp.status_code == 200

            resp2 = owner.get("/api/alert-rules")
            assert len(resp2.json()["rules"]) == 0
        finally:
            os.environ.pop("OWNERAI_FEATURE_ALERT_RULES", None)
