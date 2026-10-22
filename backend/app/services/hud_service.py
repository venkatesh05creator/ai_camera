"""Holographic HUD state and telemetry provider for Aegis Surveillance OS.

Adapted from Project JARVIS workplace HUD with live CPU/RAM/Disk metrics,
market intelligence feeds, audio visualizer telemetry, and real-time interaction logs.
"""

from __future__ import annotations

import datetime
import logging
import math
import sys
import time
from typing import Any, Dict, List, Optional

try:
    import psutil
except Exception:
    psutil = None

from .market_service import get_market_watchlist

logger = logging.getLogger(__name__)

_APP_START_TIME = time.time()
_CHAT_COUNTER = 2
_COMMANDS_RUN = 3
_LAST_TOOL = "Perimeter Scanner"
_CURRENT_STATE = "idle"
_LAST_USER = ""
_LAST_ASSISTANT = "Perimeter armed. All vision nodes operational."

_HUD_CHAT_HISTORY: List[Dict[str, Any]] = [
    {
        "i": 1,
        "k": "sys",
        "x": "Holographic 3D HUD online. Neural visual pipelines linked at 30 FPS.",
        "t": datetime.datetime.now().strftime("%H:%M"),
    },
    {
        "i": 2,
        "k": "jarvis",
        "x": "All biometric models calibrated. Visual perimeter armed and ready.",
        "t": datetime.datetime.now().strftime("%H:%M"),
    },
]

_HUD_CARDS: List[Dict[str, Any]] = [
    {
        "i": 1,
        "title": "Autonomous Surveillance",
        "t": "LIVE",
        "body": "Continuous multi-camera verification, 512-dim FaceNet biometrics, and anonymous object tracking active.",
    },
    {
        "i": 2,
        "title": "Executive Automation",
        "t": "READY",
        "body": "WhatsApp messaging, YouTube media playback, application launching, and mail briefings armed.",
    },
]


def update_hud_activity(
    user_query: str,
    assistant_reply: str,
    tool_name: Optional[str] = None,
    state: str = "idle",
) -> None:
    """Updates the live interaction logs and state displayed on the Holographic HUD."""
    global _CHAT_COUNTER, _COMMANDS_RUN, _LAST_TOOL, _CURRENT_STATE, _LAST_USER, _LAST_ASSISTANT

    now_str = datetime.datetime.now().strftime("%H:%M")
    _LAST_USER = user_query
    _LAST_ASSISTANT = assistant_reply
    _CURRENT_STATE = state

    if tool_name:
        _LAST_TOOL = tool_name
        _COMMANDS_RUN += 1

    if user_query:
        _CHAT_COUNTER += 1
        _HUD_CHAT_HISTORY.append({
            "i": _CHAT_COUNTER,
            "k": "you",
            "x": user_query,
            "t": now_str,
        })

    if assistant_reply:
        _CHAT_COUNTER += 1
        _HUD_CHAT_HISTORY.append({
            "i": _CHAT_COUNTER,
            "k": "jarvis",
            "x": assistant_reply[:240],
            "t": now_str,
        })

    # Keep chat history bounded
    if len(_HUD_CHAT_HISTORY) > 60:
        _HUD_CHAT_HISTORY.pop(0)


def get_hud_state_data(lv: int = 0) -> Dict[str, Any]:
    """Generates the full telemetry payload required by the 3D Holographic HUD."""
    # 1. System vitals via psutil (with fallback)
    cpu = 18.5
    ram = 42.0
    disk_pct = 45.0
    disk_free_gb = 145.0
    battery_pct: Optional[int] = 95
    power_plugged: Optional[bool] = True

    if psutil is not None:
        try:
            cpu = psutil.cpu_percent(interval=None) or 15.0
            ram = psutil.virtual_memory().percent or 40.0
            disk_path = "C:\\" if sys.platform == "win32" else "/"
            du = psutil.disk_usage(disk_path)
            disk_pct = du.percent
            disk_free_gb = round(du.free / (1024 ** 3), 1)
            bat = psutil.sensors_battery()
            if bat is not None:
                battery_pct = int(bat.percent)
                power_plugged = bool(bat.power_plugged)
        except Exception as exc:
            logger.debug("psutil telemetry exception: %s", exc)

    uptime_secs = int(time.time() - _APP_START_TIME)

    # 2. Market watchlist from market_service
    stocks_out: List[Dict[str, Any]] = []
    try:
        raw_stocks = get_market_watchlist()
        for s in raw_stocks:
            stocks_out.append({
                "sym": s.get("symbol"),
                "name": s.get("name"),
                "price": s.get("price"),
                "pct": s.get("pct_change", 0.0),
                "mom": s.get("change", 0.0),
                "above": s.get("pct_change", 0.0) >= 0,
                "spark": s.get("spark", [s.get("price", 100)]),
                "signal": s.get("signal", "HOLD"),
                "err": False,
                "stale": s.get("stale", False),
            })
    except Exception as exc:
        logger.debug("Failed to assemble market quotes for HUD: %s", exc)

    # 3. Dynamic audio wave synthesis
    t = time.time()
    amp = 0.35 if _CURRENT_STATE == "speaking" else 0.12
    wave_samples = [
        round(max(0.02, min(0.98, amp * (0.5 + 0.5 * math.sin(t * 8 + i * 0.9)))), 3)
        for i in range(8)
    ]

    return {
        "state": _CURRENT_STATE,
        "note": "QUANTUM CORE ACTIVE" if _CURRENT_STATE == "idle" else f"PROCESSING {_CURRENT_STATE.upper()}",
        "mode": "hybrid",
        "last_you": _LAST_USER,
        "last_jarvis": _LAST_ASSISTANT,
        "stocks": stocks_out,
        "mic": {
            "n": lv + 1,
            "a": wave_samples,
        },
        "sys": {
            "cpu": cpu,
            "ram": ram,
            "disk": disk_pct,
            "free": disk_free_gb,
            "bat": battery_pct,
            "plug": power_plugged,
            "up": uptime_secs,
        },
        "vitals": {
            "cpu": cpu,
            "ram": ram,
            "disk": disk_pct,
            "uptime": f"{uptime_secs // 3600}h {(uptime_secs % 3600) // 60}m",
        },
        "cards": _HUD_CARDS,
        "chat": list(_HUD_CHAT_HISTORY),
        "model": "Groq / Llama-3.3 + Aegis Local Vision",
        "t_rec": 0.4,
        "t_think": 0.3,
        "last_tool": _LAST_TOOL,
        "tools": str(_COMMANDS_RUN),
        "facts": "12",
        "mail_age": 4,
        "tool_active": _CURRENT_STATE in ("speaking", "thinking"),
    }
