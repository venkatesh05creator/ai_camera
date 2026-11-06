"""Camera tamper & health detection (Phase 3 item #5, Phase 3B rank #1).

Probes a camera stream for degradation and tampering:

* blur          - Laplacian variance below threshold
* low_light     - mean brightness below threshold
* tampered      - lens covered (very low brightness AND low variance)
* frozen        - no fresh frame for ``camera_health_frozen_seconds``

Everything is metadata-only: probes run on the latest frame in memory and
persist a :class:`~ownerai.models.CameraHealthCheck` record.  Raw frames are
never stored.

Ships behind the ``CAMERA_HEALTH`` feature flag.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np

try:  # OpenCV is optional - the biometric engine may not be installed
    import cv2

    _HAS_OPENCV = True
except Exception:  # pragma: no cover - exercised only without the vision stack
    cv2 = None  # type: ignore[assignment]
    _HAS_OPENCV = False

from ..db import session_scope
from ..features import is_enabled
from ..models import CameraHealthCheck, Device
from ..settings import Settings, get_settings

logger = logging.getLogger(__name__)


class HealthError(RuntimeError):
    """Raised when a health probe cannot run."""


@dataclass
class ProbeResult:
    """Outcome of a single health probe."""

    ok: bool
    status: str  # healthy | tampered | blurry | low_light | frozen
    detail: str
    metrics: dict[str, float]


@dataclass
class HealthReport:
    """Aggregated health report for one device."""

    device_id: int
    status: str  # overall: healthy | degraded | tampered | frozen | unknown
    checks: list[ProbeResult]
    message: str


def _laplacian_variance(frame: np.ndarray) -> float:
    """Laplacian variance of a grayscale frame (focus/blur measure)."""
    if not _HAS_OPENCV:
        raise HealthError("opencv is not installed; cannot compute blur variance")
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _mean_brightness(frame: np.ndarray) -> float:
    """Mean pixel brightness of a frame (0..255)."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    return float(gray.mean())


def probe_frame(
    frame: np.ndarray,
    *,
    settings: Optional[Settings] = None,
) -> ProbeResult:
    """Probe a single in-memory frame for blur / low light / tampering.

    Does *not* persist anything.  Returns the single most severe finding.
    """
    settings = settings or get_settings()
    if not _HAS_OPENCV:
        return ProbeResult(
            ok=False,
            status="unknown",
            detail="opencv not installed; health probes unavailable",
            metrics={},
        )

    blur_variance = _laplacian_variance(frame)
    brightness = _mean_brightness(frame)

    metrics = {"blur_variance": blur_variance, "mean_brightness": brightness}

    # Tampered: lens covered - very dark AND low texture
    if brightness < settings.camera_health_low_light_threshold and blur_variance < settings.camera_health_blur_threshold:
        return ProbeResult(
            ok=False,
            status="tampered",
            detail=(
                "possible lens cover or obstruction: "
                f"brightness={brightness:.1f}, blur_variance={blur_variance:.1f}"
            ),
            metrics=metrics,
        )
    # Blurry
    if blur_variance < settings.camera_health_blur_threshold:
        return ProbeResult(
            ok=False,
            status="blurry",
            detail=f"image is blurry: lapvariance={blur_variance:.1f}",
            metrics=metrics,
        )
    # Low light (but not fully covered)
    if brightness < settings.camera_health_low_light_threshold:
        return ProbeResult(
            ok=False,
            status="low_light",
            detail=f"low light level: brightness={brightness:.1f}",
            metrics=metrics,
        )

    return ProbeResult(
        ok=True,
        status="healthy",
        detail=f"frame healthy: brightness={brightness:.1f}, lapvariance={blur_variance:.1f}",
        metrics=metrics,
    )


def check_frozen(device: Device, *, settings: Optional[Settings] = None) -> ProbeResult:
    """Check whether a camera stream is frozen based on its last_seen_at.

    A stream is frozen when no frame/event has been observed for
    ``camera_health_frozen_seconds``.
    """
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    seen = device.last_seen_at
    if seen is None:
        return ProbeResult(
            ok=False,
            status="frozen",
            detail="no frames ever observed for this device",
            metrics={},
        )
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=timezone.utc)
    age_seconds = (now - seen).total_seconds()
    if age_seconds >= settings.camera_health_frozen_seconds:
        return ProbeResult(
            ok=False,
            status="frozen",
            detail=f"stream frozen: no frame for {age_seconds:.0f}s",
            metrics={"age_seconds": age_seconds},
        )
    return ProbeResult(
        ok=True,
        status="healthy",
        detail=f"stream live: last frame {age_seconds:.0f}s ago",
        metrics={"age_seconds": age_seconds},
    )


def run_health_check(
    device: Device,
    *,
    frame: Optional[np.ndarray] = None,
    settings: Optional[Settings] = None,
) -> HealthReport:
    """Run the full health probe set for one device.

    Persists a :class:`CameraHealthCheck` row.  Returns an aggregated report.
    """
    if not is_enabled("CAMERA_HEALTH"):
        raise HealthError("CAMERA_HEALTH feature is not enabled")
    settings = settings or get_settings()

    checks: list[ProbeResult] = []

    # Frame-based probes (blur / low light / tampered)
    if frame is not None:
        checks.append(probe_frame(frame, settings=settings))
    else:
        checks.append(
            ProbeResult(
                ok=False,
                status="unknown",
                detail="no frame supplied; frame-based probes skipped",
                metrics={},
            )
        )

    # Frozen probe (metadata only)
    checks.append(check_frozen(device, settings=settings))

    # Overall status: worst case
    severity_order = {"healthy": 0, "low_light": 1, "blurry": 2, "frozen": 3, "tampered": 4, "unknown": 5}
    worst = max(checks, key=lambda c: severity_order.get(c.status, 0))
    overall = worst.status if worst.ok is False else "healthy"
    if overall == "healthy" and not all(c.ok for c in checks):
        overall = "degraded"

    message = "; ".join(c.detail for c in checks)

    # Persist the result
    with session_scope(settings) as db:
        owner_id = device.owner_id
        record = CameraHealthCheck(
            device_id=device.id,
            owner_id=owner_id,
            status=overall,
            blur_variance=checks[0].metrics.get("blur_variance"),
            mean_brightness=checks[0].metrics.get("mean_brightness"),
            details_json=json.dumps(
                {c.status: c.detail for c in checks}
            ),
        )
        db.add(record)
        db.flush()
        record_id = record.id

    logger.info(
        "camera health check",
        extra={"device_id": device.id, "status": overall, "check_id": record_id},
    )

    return HealthReport(
        device_id=device.id,
        status=overall,
        checks=checks,
        message=message,
    )


def latest_health(device_id: int, *, settings: Optional[Settings] = None) -> Optional[dict[str, Any]]:
    """Return the most recent health check record for a device (dict)."""
    settings = settings or get_settings()
    with session_scope(settings) as db:
        row = (
            db.query(CameraHealthCheck)
            .filter_by(device_id=device_id)
            .order_by(CameraHealthCheck.checked_at.desc())
            .first()
        )
        if row is None:
            return None
        try:
            details = json.loads(row.details_json)
        except ValueError:  # pragma: no cover - defensive
            details = {}
        if not isinstance(details, dict):
            details = {}
        return {
            "id": row.id,
            "device_id": row.device_id,
            "status": row.status,
            "blur_variance": row.blur_variance,
            "mean_brightness": row.mean_brightness,
            "details": details,
            "checked_at": row.checked_at.isoformat(),
        }
