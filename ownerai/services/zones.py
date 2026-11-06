"""Privacy zones + auto-blur (Phase 3 item #4).

Owner-drawn polygonal zones on a camera are never analysed or stored as raw
frames.  Non-enrolled faces are blurred in saved clips.  Ships behind the
``PRIVACY_ZONES`` feature flag.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from ..db import session_scope
from ..features import is_enabled
from ..models import PrivacyZone
from ..settings import Settings, get_settings

logger = logging.getLogger(__name__)


class PrivacyZoneError(RuntimeError):
    """Raised when a privacy-zone operation fails."""


def point_in_polygon(point: tuple[float, float], polygon: list[list[float]]) -> bool:
    """Ray-casting point-in-polygon test.  Coordinates are normalised 0..1."""
    x, y = point
    inside = False
    n = len(polygon)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def is_in_privacy_zone(
    x: float,
    y: float,
    device_id: int,
    *,
    settings: Optional[Settings] = None,
) -> bool:
    """Return True if the normalised point (x, y) lies in any privacy zone."""
    if not is_enabled("PRIVACY_ZONES"):
        return False
    settings = settings or get_settings()
    with session_scope(settings) as db:
        zones = db.query(PrivacyZone).filter_by(device_id=device_id).all()
    for zone in zones:
        try:
            polygon = json.loads(zone.polygon_json)
        except ValueError:
            continue
        if not isinstance(polygon, list) or len(polygon) < 3:
            continue
        if point_in_polygon((x, y), polygon):
            logger.debug(
                "point in privacy zone",
                extra={"device_id": device_id, "zone": zone.name},
            )
            return True
    return False


def blur_non_enrolled_faces(*, settings: Optional[Settings] = None) -> bool:
    """Whether non-enrolled faces should be blurred in saved clips."""
    settings = settings or get_settings()
    return bool(settings.privacy_blur_enabled)
