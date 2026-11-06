"""Offline evaluation harness endpoints (Phase O-4).

Measures grounding accuracy and detects hallucinated detections in JARVIS
assistant turns, built only from stored replay-log turns and event metadata.

Ships behind the ``EVAL_HARNESS`` feature flag.
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
from ..services.eval import EvalError, evaluate_turns

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/eval", tags=["eval harness"])


def _require_eval() -> None:
    if not is_enabled("EVAL_HARNESS"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="EVAL_HARNESS feature is not enabled "
            "(set OWNERAI_FEATURE_EVAL_HARNESS=1)",
        )


@router.get("/report")
def eval_report(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, Any]:
    """Return an offline evaluation report for the owner's assistant turns."""
    _require_eval()
    try:
        report = evaluate_turns(user.id, limit=limit)
    except EvalError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return {"feature": "EVAL_HARNESS", **report.to_dict()}
