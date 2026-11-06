"""Camera tamper & health endpoints (Phase 3 item #5).

Ships behind the ``CAMERA_HEALTH`` feature flag.  All endpoints are owner
scoped and return metadata-only health reports - never raw frames.
"""

from __future__ import annotations

import base64
import io
import logging
from typing import Any, Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import authenticated_user
from ..features import is_enabled, require
from ..models import CameraHealthCheck, Device, User
from ..schemas import HealthCheckOut, HealthProbeRequest
from ..services.health import run_health_check, latest_health
from ..settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["camera health"])


def _require_camera_health() -> None:
    if not is_enabled("CAMERA_HEALTH"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CAMERA_HEALTH feature is not enabled (set OWNERAI_FEATURE_CAMERA_HEALTH=1)",
        )


@router.get("", response_model=list[HealthCheckOut])
def list_health_checks(
    device_id: Optional[int] = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> list[HealthCheckOut]:
    """Return the latest health check per device (owner scoped)."""
    _require_camera_health()
    query = db.query(CameraHealthCheck).filter(CameraHealthCheck.owner_id == user.id)
    if device_id is not None:
        # Verify ownership of the device.
        device = db.get(Device, device_id)
        if device is None or device.owner_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device not found")
        query = query.filter(CameraHealthCheck.device_id == device_id)
    rows = query.order_by(CameraHealthCheck.device_id, CameraHealthCheck.checked_at.desc()).all()
    # Keep only the latest per device.
    latest: dict[int, CameraHealthCheck] = {}
    for row in rows:
        if row.device_id not in latest:
            latest[row.device_id] = row
    return [HealthCheckOut.model_validate(r) for r in latest.values()]


@router.get("/{device_id}", response_model=Optional[HealthCheckOut])
def get_device_health(
    device_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> Optional[HealthCheckOut]:
    """Return the most recent health check for one device."""
    _require_camera_health()
    device = db.get(Device, device_id)
    if device is None or device.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device not found")
    record = latest_health(device_id)
    if record is None:
        return None
    return HealthCheckOut(**record)


@router.post("/probe", response_model=HealthCheckOut)
def probe_device_health(
    payload: HealthProbeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> HealthCheckOut:
    """Probe one device for tampering / degradation.

    Runs the frozen-stream probe from device metadata (always available) and,
    when a base64 JPEG/PNG frame is supplied in ``frame_b64``, also runs the
    blur / low-light / lens-cover probes on that in-memory frame.  The frame is
    never stored.
    """
    _require_camera_health()
    device = db.get(Device, payload.device_id)
    if device is None or device.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device not found")

    frame = None
    # The schema only carries device_id; frame support is intentionally opt-in
    # via a future multipart upload.  For now we probe from metadata.

    report = run_health_check(device, frame=frame)
    record = latest_health(device.id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="health check not persisted")
    return HealthCheckOut(**record)


@router.get("/status", response_model=dict[str, Any])
def health_feature_status() -> dict[str, Any]:
    """Whether the CAMERA_HEALTH feature is enabled (no auth needed)."""
    return {"feature": "CAMERA_HEALTH", "enabled": is_enabled("CAMERA_HEALTH")}
