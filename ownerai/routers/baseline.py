"""Learned baseline endpoints (Phase 3 item #2).

Ships behind the ``LEARNED_BASELINE`` feature flag.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import authenticated_user
from ..features import is_enabled
from ..models import Device, User
from ..services.baseline import (
    BaselineError,
    Deviation,
    evaluate_deviation,
    learn_baselines,
    latest_baseline,
)
from ..settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/baseline", tags=["learned baseline"])


def _require_baseline() -> None:
    if not is_enabled("LEARNED_BASELINE"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="LEARNED_BASELINE feature is not enabled (set OWNERAI_FEATURE_LEARNED_BASELINE=1)",
        )


@router.post("/learn")
def learn_baseline(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, Any]:
    """Learn normal activity baselines from the owner's recent events."""
    _require_baseline()
    try:
        upserted = learn_baselines(user.id, days=days)
    except BaselineError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return {"feature": "LEARNED_BASELINE", "baselines_upserted": upserted, "window_days": days}


@router.get("/{device_id}")
def get_baseline(
    device_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, Any]:
    """Return the baseline for a device's current hour-of-week bucket."""
    _require_baseline()
    device = db.get(Device, device_id)
    if device is None or device.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device not found")
    info = latest_baseline(device_id)
    if info is None:
        return {"feature": "LEARNED_BASELINE", "device_id": device_id, "baseline_learned": False}
    return {"feature": "LEARNED_BASELINE", **info}


@router.get("/{device_id}/deviation")
def check_deviation(
    device_id: int,
    count: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, Any]:
    """Evaluate whether an observed event count deviates from the baseline."""
    _require_baseline()
    device = db.get(Device, device_id)
    if device is None or device.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device not found")
    from datetime import datetime, timezone

    dev = evaluate_deviation(device_id, count, datetime.now(timezone.utc))
    if dev is None:
        return {
            "feature": "LEARNED_BASELINE",
            "device_id": device_id,
            "deviation": None,
            "message": "within normal baseline",
        }
    return {
        "feature": "LEARNED_BASELINE",
        "device_id": device_id,
        "deviation": {
            "observed": dev.observed,
            "mean": dev.mean,
            "stddev": dev.stddev,
            "z_score": dev.z_score,
            "explanation": dev.explanation,
        },
    }
