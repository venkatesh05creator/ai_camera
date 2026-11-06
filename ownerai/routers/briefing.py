"""Overnight security briefing endpoints (Phase O-2).

Returns a spoken + written narrative summary of stored camera events,
built only from event metadata.  Ships behind the ``SECURITY_BRIEFING``
feature flag.
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
from ..services.briefing import BriefingError, generate_briefing

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/briefing", tags=["security briefing"])


def _require_briefing() -> None:
    if not is_enabled("SECURITY_BRIEFING"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SECURITY_BRIEFING feature is not enabled "
            "(set OWNERAI_FEATURE_SECURITY_BRIEFING=1)",
        )


@router.get("/security")
def security_briefing(
    period: str = Query(default="daily", pattern="^(daily|weekly)$"),
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, Any]:
    """Generate a narrative security briefing for the owner."""
    _require_briefing()
    try:
        briefing = generate_briefing(user.id, period=period)
    except BriefingError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return {"feature": "SECURITY_BRIEFING", **briefing.to_dict()}
