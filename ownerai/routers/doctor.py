"""Doctor / benchmark endpoints (Phase 3B rank #6).

Ships behind the ``DOCTOR`` feature flag.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import authenticated_user
from ..features import is_enabled
from ..models import User
from ..services.doctor import DoctorError, benchmark_provider, run_doctor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/doctor", tags=["doctor"])


def _require_doctor() -> None:
    if not is_enabled("DOCTOR"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="DOCTOR feature is not enabled (set OWNERAI_FEATURE_DOCTOR=1)",
        )


@router.get("")
def doctor(
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict:
    """Run all health probes and return an aggregated report."""
    _require_doctor()
    try:
        report = run_doctor()
    except DoctorError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return report.to_dict()


@router.get("/benchmark")
def benchmark(
    runs: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict:
    """Benchmark the AI provider."""
    _require_doctor()
    try:
        return benchmark_provider(runs=runs)
    except DoctorError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
