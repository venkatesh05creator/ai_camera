"""Holographic Iron Man HUD and live telemetry endpoints for Project JARVIS."""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import psutil
except Exception:
    psutil = None
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
    hud_file = TEMPLATES_DIR / "hud.html"
    if hud_file.exists():
        return HTMLResponse(content=hud_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h2>HUD Template Not Found</h2>", status_code=404)


@router.get("/api/hud/state")
@router.get("/api/state")
def get_hud_state(lv: int = 0) -> JSONResponse:
    """Returns live telemetry, system vitals, mic wave, and market quotes for the HUD."""
    try:
        from backend.app.services.hud_service import get_hud_state_data
        return JSONResponse(get_hud_state_data(lv=lv))
    except Exception as exc:
        logger.warning("HUD state provider exception: %s", exc)
        return JSONResponse({"state": "idle", "sys": {"cpu": 10, "ram": 25, "disk": 40}, "stocks": []})
