"""Holographic Iron Man HUD and live telemetry endpoints for Project JARVIS."""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..sessions import current_session_from_request
from ..settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["hud"])

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Application start time for uptime tracking
_APP_START_TIME = time.time()

# Ephemeral state tracking
_LAST_USER_QUERY = "Jarvis, status report."
_LAST_JARVIS_RESPONSE = "All systems operational. Security perimeter armed, visual recognition active."
_CURRENT_STATE = "idle"


def set_assistant_activity(user_query: str, jarvis_reply: str, state: str = "idle") -> None:
    """Updates the live activity state displayed on the Holographic HUD."""
    global _LAST_USER_QUERY, _LAST_JARVIS_RESPONSE, _CURRENT_STATE
    _LAST_USER_QUERY = user_query
    _LAST_JARVIS_RESPONSE = jarvis_reply
    _CURRENT_STATE = state


@router.get("/hud", response_class=HTMLResponse)
def get_hud_page(request: Request, db: Session = Depends(get_db)) -> Any:
    """Renders the 3D Holographic Iron Man HUD."""
    session = current_session_from_request(request, db)
    if session is None or session.user is None:
        return RedirectResponse(url="/login?next=/hud", status_code=302)

    context = {
        "request": request,
        "user": session.user,
        "csrf_token": session.csrf_token,
        "app_name": get_settings().app_name,
    }
    return templates.TemplateResponse("hud.html", context)


@router.get("/api/hud/state")
@router.get("/api/state")
def get_hud_state(lv: int = 0) -> JSONResponse:
    """Returns live telemetry, system vitals, mic wave, and market quotes for the HUD."""
    # 1. System vitals via psutil
    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory().percent
    try:
        disk_path = "C:\\" if sys.platform == "win32" else "/"
        disk = psutil.disk_usage(disk_path).percent
    except Exception:
        disk = 45.0

    uptime_secs = int(time.time() - _APP_START_TIME)
    hours, rem = divmod(uptime_secs, 3600)
    mins, _ = divmod(rem, 60)
    uptime_str = f"{hours}h {mins}m"

    # 2. Market watchlist from market_service
    stocks_out: List[Dict[str, Any]] = []
    try:
        from backend.app.services.market_service import get_market_watchlist
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

    # 3. Audio visualizer wave simulation
    mic_wave = [0.05, 0.12, 0.28, 0.35, 0.22, 0.14, 0.06]

    return JSONResponse({
        "state": _CURRENT_STATE,
        "note": "QUANTUM CORE ACTIVE",
        "mode": "hybrid",
        "last_you": _LAST_USER_QUERY,
        "last_jarvis": _LAST_JARVIS_RESPONSE,
        "stocks": stocks_out,
        "mic": {
            "n": lv + 1,
            "a": mic_wave,
        },
        "vitals": {
            "cpu": cpu,
            "ram": ram,
            "disk": disk,
            "uptime": uptime_str,
        },
    })
