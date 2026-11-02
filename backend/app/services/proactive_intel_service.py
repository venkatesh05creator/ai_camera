"""Universal Jarvis AI Command Center — Proactive Intelligence & Notifications Engine
Continuously evaluates conditions (cameras, severe weather, security triggers,
system anomalies) and generates prioritized, deduplicated notifications with snooze
and dismiss controls.
"""

import time
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# In-memory proactive notifications store (isolated and persistent across queries)
_NOTIFICATIONS: List[Dict[str, Any]] = []
_SNOOZED: Dict[str, float] = {}  # category -> snooze_until_timestamp
_LAST_DISPATCHED: Dict[str, float] = {}  # category -> last_time
_DEDUPLICATION_WINDOW_SECONDS = 900  # 15 minutes


class ProactiveIntelService:
    """Evaluates real-time feeds and triggers intelligent proactive notifications."""

    @classmethod
    def evaluate_system_conditions(
        cls,
        active_cameras_count: int = 1,
        system_cpu_percent: float = 25.0,
        unacknowledged_alerts_count: int = 0,
        weather_aqi: Optional[int] = 42,
    ) -> List[Dict[str, Any]]:
        """Run proactive condition checks against genuine telemetry."""
        now = time.time()
        new_notifications: List[Dict[str, Any]] = []

        # 1. Camera Health Check
        if active_cameras_count == 0:
            category = "camera_offline"
            if cls._can_dispatch(category, now):
                new_notifications.append(cls._create_notification(
                    title="All Camera Feeds Offline",
                    message="No active camera streams are currently streaming. Check hardware connection and permissions.",
                    category="camera",
                    priority="CRITICAL",
                    evidence={"active_cameras": 0},
                ))
                _LAST_DISPATCHED[category] = now

        # 2. Environmental Hazard Check (AQI > 150)
        if weather_aqi and weather_aqi > 150:
            category = "environmental_hazard"
            if cls._can_dispatch(category, now):
                new_notifications.append(cls._create_notification(
                    title="Air Quality Hazard Detected",
                    message=f"Current regional AQI has reached {weather_aqi} (Unhealthy). Indoor air filtration recommended.",
                    category="weather",
                    priority="WARNING",
                    evidence={"aqi": weather_aqi},
                ))
                _LAST_DISPATCHED[category] = now

        # 3. Security Alerts Spike
        if unacknowledged_alerts_count > 5:
            category = "security_surge"
            if cls._can_dispatch(category, now):
                new_notifications.append(cls._create_notification(
                    title="High Security Activity Detected",
                    message=f"There are {unacknowledged_alerts_count} unacknowledged security triggers across your perimeter.",
                    category="security",
                    priority="HIGH",
                    evidence={"unacknowledged_alerts": unacknowledged_alerts_count},
                ))
                _LAST_DISPATCHED[category] = now

        # 4. System Resource Exhaustion (CPU > 90%)
        if system_cpu_percent > 90.0:
            category = "resource_exhaustion"
            if cls._can_dispatch(category, now):
                new_notifications.append(cls._create_notification(
                    title="System Resource Alert",
                    message=f"Host CPU consumption has spiked to {system_cpu_percent}%. Potential runaway process.",
                    category="system",
                    priority="WARNING",
                    evidence={"cpu_percent": system_cpu_percent},
                ))
                _LAST_DISPATCHED[category] = now

        for n in new_notifications:
            _NOTIFICATIONS.insert(0, n)

        # Cap memory at 100 notifications
        if len(_NOTIFICATIONS) > 100:
            _NOTIFICATIONS[:] = _NOTIFICATIONS[:100]

        return new_notifications

    @classmethod
    def _can_dispatch(cls, category: str, now: float) -> bool:
        """Check if alert is currently snoozed or within deduplication window."""
        snooze_until = _SNOOZED.get(category, 0)
        if now < snooze_until:
            return False

        last_time = _LAST_DISPATCHED.get(category, 0)
        if (now - last_time) < _DEDUPLICATION_WINDOW_SECONDS:
            return False

        return True

    @classmethod
    def _create_notification(
        cls,
        title: str,
        message: str,
        category: str,
        priority: str,
        evidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "id": f"notif_{uuid.uuid4().hex[:8]}",
            "title": title,
            "message": message,
            "category": category,
            "priority": priority,  # CRITICAL, HIGH, WARNING, INFO
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "acknowledged": False,
            "evidence": evidence,
        }

    @classmethod
    def get_notifications(cls, limit: int = 30) -> List[Dict[str, Any]]:
        """Retrieve recent proactive notifications."""
        return _NOTIFICATIONS[:limit]

    @classmethod
    def acknowledge_notification(cls, notification_id: str) -> bool:
        """Mark a notification as acknowledged."""
        for n in _NOTIFICATIONS:
            if n["id"] == notification_id:
                n["acknowledged"] = True
                return True
        return False

    @classmethod
    def snooze_category(cls, category: str, minutes: int = 30) -> None:
        """Snooze notifications of a given category."""
        _SNOOZED[category] = time.time() + (minutes * 60)

    @classmethod
    def dismiss_notification(cls, notification_id: str) -> bool:
        """Dismiss a notification from the active queue."""
        for i, n in enumerate(_NOTIFICATIONS):
            if n["id"] == notification_id:
                _NOTIFICATIONS.pop(i)
                return True
        return False
