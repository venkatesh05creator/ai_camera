"""Natural-language alert rules (Phase 3 item #3).

Parses owner phrasing like ``"Alert me if someone I haven't enrolled is at
the door after 11pm"`` into a validated, structured rule.  The rule is stored
but not activated until the owner explicitly confirms it.

Ships behind the ``ALERT_RULES`` feature flag.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import authenticated_user
from ..features import is_enabled
from ..models import AlertRule, Device, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alert-rules", tags=["alert rules"])

#: Times mentioned in NL rules (24-hour).
_TIME_RE = re.compile(r"\b(\d{1,2})\s*(?::(\d{2}))?\s*(am|pm)?\b", re.IGNORECASE)

#: Camera/location hints.
_CAMERA_HINTS = {
    "door": ["door", "front door", "entrance"],
    "gate": ["gate"],
    "driveway": ["driveway"],
}

_MAX_RULES_PER_OWNER = 20


def _require_alert_rules() -> None:
    if not is_enabled("ALERT_RULES"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ALERT_RULES feature is not enabled (set OWNERAI_FEATURE_ALERT_RULES=1)",
        )


def _parse_time(nl: str) -> dict[str, Any] | None:
    """Extract a time constraint from NL, e.g. 'after 11pm' → {after: 23:00}."""
    m = _TIME_RE.search(nl)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    meridian = (m.group(3) or "").lower()
    if meridian == "pm" and hour != 12:
        hour += 12
    if meridian == "am" and hour == 12:
        hour = 0
    t = time(hour, minute)
    nl_lower = nl.lower()
    if "after" in nl_lower:
        return {"after": t.isoformat(timespec="minutes")}
    if "before" in nl_lower:
        return {"before": t.isoformat(timespec="minutes")}
    if "at" in nl_lower:
        return {"at": t.isoformat(timespec="minutes")}
    return {"at": t.isoformat(timespec="minutes")}


def _parse_camera(nl: str) -> str | None:
    nl_lower = nl.lower()
    for camera, hints in _CAMERA_HINTS.items():
        for hint in hints:
            if hint in nl_lower:
                return camera
    return None


def _parse_condition(nl: str) -> str:
    nl_lower = nl_lower = nl.lower()
    if "haven't enrolled" in nl_lower or "not enrolled" in nl_lower or "unenrolled" in nl_lower:
        return "unenrolled_person"
    if "person" in nl_lower:
        return "person"
    if "motion" in nl_lower:
        return "motion"
    return "any_activity"


def parse_nl_rule(nl: str) -> dict[str, Any]:
    """Parse a natural-language rule into a structured dict.

    Never executes anything - just validates and structures the owner's
    intent so it can be reviewed before confirmation.
    """
    parsed: dict[str, Any] = {
        "condition": _parse_condition(nl),
        "camera": _parse_camera(nl),
    }
    time_constraint = _parse_time(nl)
    if time_constraint:
        parsed["time"] = time_constraint
    action = "alert"
    parsed["action"] = action
    return parsed


@router.post("")
def create_alert_rule(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, Any]:
    """Parse a natural-language rule and store it (unconfirmed).

    Body: ``{"name": "...", "nl": "Alert me if ..."}``
    """
    _require_alert_rules()
    name = str(payload.get("name", "")).strip()[:160]
    nl = str(payload.get("nl", "")).strip()
    if not name or not nl:
        raise HTTPException(status_code=422, detail="name and nl are required")

    existing = (
        db.query(AlertRule).filter_by(owner_id=user.id).count()
    )
    if existing >= _MAX_RULES_PER_OWNER:
        raise HTTPException(status_code=400, detail="alert rule limit reached")

    parsed = parse_nl_rule(nl)
    # Validate that any referenced camera exists.
    camera = parsed.get("camera")
    if camera:
        device = (
            db.query(Device)
            .filter_by(owner_id=user.id)
            .filter(Device.name.ilike(f"%{camera}%"))
            .first()
        )
        if device is None:
            raise HTTPException(
                status_code=422,
                detail=f"no camera matching '{camera}' found for this owner",
            )
        parsed["camera_device_id"] = device.id

    rule = AlertRule(
        owner_id=user.id,
        name=name,
        raw_nl=nl,
        parsed_json=json.dumps(parsed),
        enabled=False,
        confirmed_by_owner=False,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return {
        "id": rule.id,
        "name": rule.name,
        "raw_nl": rule.raw_nl,
        "parsed": parsed,
        "enabled": rule.enabled,
        "confirmed_by_owner": rule.confirmed_by_owner,
        "message": "Rule stored. Confirm it with POST /api/alert-rules/{id}/confirm before it activates.",
    }


@router.get("")
def list_alert_rules(
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, Any]:
    """List the owner's alert rules."""
    _require_alert_rules()
    rows = (
        db.query(AlertRule)
        .filter_by(owner_id=user.id)
        .order_by(AlertRule.created_at.desc())
        .all()
    )
    return {
        "feature": "ALERT_RULES",
        "rules": [
            {
                "id": r.id,
                "name": r.name,
                "raw_nl": r.raw_nl,
                "parsed": json.loads(r.parsed_json or "{}"),
                "enabled": r.enabled,
                "confirmed_by_owner": r.confirmed_by_owner,
                "trigger_count": r.trigger_count,
                "last_triggered_at": r.last_triggered_at.isoformat()
                if r.last_triggered_at
                else None,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }


@router.post("/{rule_id}/confirm")
def confirm_alert_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, Any]:
    """Owner confirms a rule, activating it."""
    _require_alert_rules()
    rule = db.get(AlertRule, rule_id)
    if rule is None or rule.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="rule not found")
    from datetime import datetime, timezone

    rule.confirmed_by_owner = True
    rule.enabled = True
    rule.confirmed_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "id": rule.id,
        "name": rule.name,
        "confirmed_by_owner": True,
        "enabled": True,
        "message": "Rule confirmed and active.",
    }


@router.delete("/{rule_id}")
def delete_alert_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, bool]:
    """Delete one of the owner's alert rules."""
    _require_alert_rules()
    rule = db.get(AlertRule, rule_id)
    if rule is None or rule.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="rule not found")
    db.delete(rule)
    db.commit()
    return {"ok": True}
