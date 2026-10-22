"""Zone & Region-of-Interest (ROI) Rule Engine.

Monitors spatial intrusion, directional boundary crossing (entry/exit tripwires),
occupancy thresholds, and loitering with deduplication keys and cooldown suppressions.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np


@dataclass
class ZoneRule:
    zone_id: str
    camera_id: str
    name: str
    polygon: List[Tuple[float, float]]  # Normalized points [[x1, y1], [x2, y2], ...] (0.0 to 1.0)
    rule_type: str = "entry"  # "entry", "exit", "occupancy", "loitering"
    target_classes: List[str] = field(default_factory=lambda: ["person"])
    max_count: int = 1
    loiter_seconds: float = 10.0
    cooldown_seconds: float = 30.0
    severity: str = "medium"  # "low", "medium", "high", "critical"
    is_active: bool = True


@dataclass
class ZoneAlertEvent:
    alert_id: str
    zone_id: str
    camera_id: str
    rule_name: str
    event_type: str
    object_label: str
    track_id: Optional[str]
    confidence: float
    timestamp: float
    description: str
    severity: str
    requires_verification: bool = True


class ZoneEngine:
    """Evaluates spatial zone rules against active object tracks with deduplication."""

    def __init__(self):
        self.rules: Dict[str, ZoneRule] = {}
        # Track previous locations: {track_id: (center_x, center_y, timestamp)}
        self.track_history: Dict[str, Tuple[float, float, float]] = {}
        # Dwell time tracking: {(zone_id, track_id): entry_timestamp}
        self.dwell_tracker: Dict[Tuple[str, str], float] = {}
        # Cooldown tracking: {cooldown_key: last_alert_timestamp}
        self.cooldowns: Dict[str, float] = {}

    def register_rule(self, rule: ZoneRule):
        self.rules[rule.zone_id] = rule

    def remove_rule(self, zone_id: str):
        if zone_id in self.rules:
            del self.rules[zone_id]

    def _is_inside(self, point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
        """Check if normalized point (px, py) is inside polygon using cv2.pointPolygonTest."""
        pts = np.array(polygon, dtype=np.float32)
        # pointPolygonTest expects 2D contour in shape (N, 1, 2)
        contour = pts.reshape((-1, 1, 2))
        res = cv2.pointPolygonTest(contour, point, False)
        return res >= 0

    def evaluate_tracks(
        self,
        camera_id: str,
        tracks: List[Any],  # TrackedObject or objects with bbox and track_id
        frame_width: int = 1280,
        frame_height: int = 720,
    ) -> List[ZoneAlertEvent]:
        """Evaluate all active rules for this camera and return deduplicated triggered alerts."""
        now = time.time()
        triggered_alerts: List[ZoneAlertEvent] = []

        active_rules = [
            r for r in self.rules.values()
            if r.camera_id == camera_id and r.is_active
        ]
        if not active_rules:
            return []

        # Map current positions
        current_positions: Dict[str, Tuple[float, float]] = {}
        for trk in tracks:
            bx, by, bw, bh = trk.bbox
            # Use centroid of the bounding box
            norm_x = (bx + bw / 2.0) / float(frame_width)
            norm_y = (by + bh / 2.0) / float(frame_height)
            tid = str(getattr(trk, "track_id", id(trk)))
            current_positions[tid] = (norm_x, norm_y)

        for rule in active_rules:
            inside_tracks: List[str] = []

            for tid, (nx, ny) in current_positions.items():
                is_currently_in = self._is_inside((nx, ny), rule.polygon)
                prev_pos = self.track_history.get(tid)

                if is_currently_in:
                    inside_tracks.append(tid)

                # Entry detection: was outside previously, now inside
                if rule.rule_type == "entry":
                    was_outside = prev_pos is None or not self._is_inside((prev_pos[0], prev_pos[1]), rule.polygon)
                    if is_currently_in and was_outside:
                        cooldown_key = f"{rule.zone_id}:entry:{tid}"
                        if (now - self.cooldowns.get(cooldown_key, 0.0)) > rule.cooldown_seconds:
                            self.cooldowns[cooldown_key] = now
                            triggered_alerts.append(
                                ZoneAlertEvent(
                                    alert_id=f"alert_{int(now * 1000)}",
                                    zone_id=rule.zone_id,
                                    camera_id=camera_id,
                                    rule_name=rule.name,
                                    event_type="zone_entry",
                                    object_label="person",
                                    track_id=tid,
                                    confidence=0.92,
                                    timestamp=now,
                                    description=f"Entry detected in zone '{rule.name}' by track {tid}.",
                                    severity=rule.severity,
                                )
                            )

                # Exit detection: was inside previously, now outside
                elif rule.rule_type == "exit":
                    was_inside = prev_pos is not None and self._is_inside((prev_pos[0], prev_pos[1]), rule.polygon)
                    if was_inside and not is_currently_in:
                        cooldown_key = f"{rule.zone_id}:exit:{tid}"
                        if (now - self.cooldowns.get(cooldown_key, 0.0)) > rule.cooldown_seconds:
                            self.cooldowns[cooldown_key] = now
                            triggered_alerts.append(
                                ZoneAlertEvent(
                                    alert_id=f"alert_{int(now * 1000)}",
                                    zone_id=rule.zone_id,
                                    camera_id=camera_id,
                                    rule_name=rule.name,
                                    event_type="zone_exit",
                                    object_label="person",
                                    track_id=tid,
                                    confidence=0.90,
                                    timestamp=now,
                                    description=f"Exit detected from zone '{rule.name}' by track {tid}.",
                                    severity=rule.severity,
                                )
                            )

                # Loitering / Prolonged Presence
                elif rule.rule_type == "loitering":
                    dwell_key = (rule.zone_id, tid)
                    if is_currently_in:
                        entry_time = self.dwell_tracker.setdefault(dwell_key, now)
                        dwell_duration = now - entry_time
                        if dwell_duration >= rule.loiter_seconds:
                            cooldown_key = f"{rule.zone_id}:loiter:{tid}"
                            if (now - self.cooldowns.get(cooldown_key, 0.0)) > rule.cooldown_seconds:
                                self.cooldowns[cooldown_key] = now
                                triggered_alerts.append(
                                    ZoneAlertEvent(
                                        alert_id=f"alert_{int(now * 1000)}",
                                        zone_id=rule.zone_id,
                                        camera_id=camera_id,
                                        rule_name=rule.name,
                                        event_type="zone_loitering",
                                        object_label="person",
                                        track_id=tid,
                                        confidence=0.88,
                                        timestamp=now,
                                        description=f"Loitering alert: track {tid} present in '{rule.name}' for {int(dwell_duration)}s.",
                                        severity=rule.severity,
                                    )
                                )
                    else:
                        if dwell_key in self.dwell_tracker:
                            del self.dwell_tracker[dwell_key]

            # Occupancy Threshold Rule
            if rule.rule_type == "occupancy" and len(inside_tracks) > rule.max_count:
                cooldown_key = f"{rule.zone_id}:occupancy"
                if (now - self.cooldowns.get(cooldown_key, 0.0)) > rule.cooldown_seconds:
                    self.cooldowns[cooldown_key] = now
                    triggered_alerts.append(
                        ZoneAlertEvent(
                            alert_id=f"alert_{int(now * 1000)}",
                            zone_id=rule.zone_id,
                            camera_id=camera_id,
                            rule_name=rule.name,
                            event_type="zone_occupancy_exceeded",
                            object_label="person",
                            track_id=None,
                            confidence=0.95,
                            timestamp=now,
                            description=f"Zone '{rule.name}' occupancy exceeded: {len(inside_tracks)} objects present (threshold: {rule.max_count}).",
                            severity=rule.severity,
                        )
                    )

        # Update historical positions
        for tid, (nx, ny) in current_positions.items():
            self.track_history[tid] = (nx, ny, now)

        # Clean up stale track history (> 60s)
        stale_tids = [tid for tid, (_, _, ts) in self.track_history.items() if (now - ts) > 60.0]
        for tid in stale_tids:
            del self.track_history[tid]

        return triggered_alerts


zone_engine = ZoneEngine()
