"""Wake word endpoints (Phase 3B rank #3).

Ships behind the ``WAKE_WORD`` feature flag.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import authenticated_user
from ..features import is_enabled
from ..models import User
from ..services.wake_word import _wake_word
from ..settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wake-word", tags=["wake word"])


def _require_wake_word() -> None:
    if not is_enabled("WAKE_WORD"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="WAKE_WORD feature is not enabled (set OWNERAI_FEATURE_WAKE_WORD=1)",
        )


@router.post("/detected")
def register_wake_word(
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict:
    """Client reports a wake word detection.

    Body: ``{"session_id": "...", "device_id": "...", "ttl_seconds": 30}``
    """
    _require_wake_word()
    session_id = str(payload.get("session_id", ""))
    device_id = str(payload.get("device_id", ""))
    ttl = int(payload.get("ttl_seconds", 30) or 30)
    if not session_id or not device_id:
        raise HTTPException(status_code=422, detail="session_id and device_id required")
    session = _wake_word.register_wake_word(session_id, device_id, ttl)
    if session is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="wake word disabled")
    return {
        "feature": "WAKE_WORD",
        "session_id": session.session_id,
        "expires_at": session.expires_at.isoformat(),
    }


@router.get("/sessions")
def list_sessions(
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict:
    """List active wake word sessions."""
    _require_wake_word()
    return {"feature": "WAKE_WORD", "sessions": _wake_word.list_active_sessions()}
