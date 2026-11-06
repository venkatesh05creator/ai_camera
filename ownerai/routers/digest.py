"""Daily/weekly digest endpoints (Phase 3 item #6).

Ships behind the ``DIGEST`` feature flag.
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
from ..services.digest import generate_digest, latest_digest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/digest", tags=["digest"])


def _require_digest() -> None:
    if not is_enabled("DIGEST"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="DIGEST feature is not enabled (set OWNERAI_FEATURE_DIGEST=1)",
        )


@router.post("")
def create_digest(
    period: str = Query(default="daily", pattern="^(daily|weekly)$"),
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, Any]:
    """Generate a narrative digest for the owner."""
    _require_digest()
    digest = generate_digest(user.id, period=period)
    return {
        "feature": "DIGEST",
        "id": digest.id,
        "period": digest.period,
        "narrative": digest.narrative,
        "event_count": digest.event_count,
        "started_at": digest.started_at.isoformat(),
        "ended_at": digest.ended_at.isoformat(),
    }


@router.get("")
def get_digest(
    period: str = Query(default="daily", pattern="^(daily|weekly)$"),
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, Any]:
    """Return the latest digest for the owner/period."""
    _require_digest()
    info = latest_digest(user.id, period=period)
    if info is None:
        return {"feature": "DIGEST", "period": period, "narrative": None, "event_count": 0}
    return {"feature": "DIGEST", **info}
