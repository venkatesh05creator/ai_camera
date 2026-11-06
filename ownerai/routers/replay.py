"""Per-turn replay / audit log endpoints (Phase 3B rank #4).

Ships behind the ``REPLAY_LOG`` feature flag.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import authenticated_user
from ..features import is_enabled
from ..models import User
from ..services.replay import ReplayLog
from ..settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/replay", tags=["replay log"])

_replay = ReplayLog()


def _require_replay() -> None:
    if not is_enabled("REPLAY_LOG"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="REPLAY_LOG feature is not enabled (set OWNERAI_FEATURE_REPLAY_LOG=1)",
        )


@router.get("/turns")
def list_turns(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, Any]:
    """Return recent assistant turns for the owner (replay log)."""
    _require_replay()
    turns = _replay.list_turns(user.id, limit=limit, offset=offset)
    return {"feature": "REPLAY_LOG", "turns": turns, "count": len(turns)}
