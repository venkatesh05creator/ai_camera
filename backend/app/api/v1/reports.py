"""Analytics and reporting router."""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import PERM_REPORTS_READ, has_permission
from ...models.entities import User
from ...schemas.schemas import ReportSummary
from ...services.audit_service import log_action
from ...services.report_service import generate_summary_report
from .auth import get_current_user

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/summary", response_model=ReportSummary)
def get_report_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not has_permission(current_user.role, PERM_REPORTS_READ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    data = generate_summary_report(db)
    return ReportSummary.model_validate(data)


@router.get("/export")
def export_events_csv(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Export detection event logs as a CSV report."""
    if not has_permission(current_user.role, PERM_REPORTS_READ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    from ...services.event_service import query_events

    events = query_events(db, limit=1000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Event ID", "Camera ID", "Timestamp UTC", "Type", "Track ID", "Person ID", "Confidence", "Review Status"])

    for e in events:
        writer.writerow([
            e.id,
            e.camera_id,
            e.occurred_at.isoformat(),
            e.event_type,
            e.track_id or "N/A",
            e.person_id or "Anonymous",
            f"{e.confidence:.2f}",
            e.review_status,
        ])

    log_action(db, action="reports.export_csv", resource_type="report", actor_user_id=current_user.id)
    csv_bytes = output.getvalue().encode("utf-8")
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="surveillance_report.csv"'},
    )
