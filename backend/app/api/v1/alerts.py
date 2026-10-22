"""Actionable alerts and notifications router."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...models.entities import Alert, User
from ...schemas.schemas import AlertOut
from ...services.audit_service import log_action
from .auth import get_current_user

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=List[AlertOut])
def get_alerts(
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Alert).order_by(desc(Alert.created_at))
    if status:
        stmt = stmt.where(Alert.status == status)
    alerts = db.scalars(stmt.limit(limit)).all()
    return [AlertOut.model_validate(a) for a in alerts]


@router.put("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(alert_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = "acknowledged"
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)

    log_action(db, action="alert.acknowledge", resource_type="alert", actor_user_id=current_user.id, resource_id=alert.id)
    return alert


@router.put("/{alert_id}/resolve", response_model=AlertOut)
def resolve_alert(alert_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = "resolved"
    alert.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)

    log_action(db, action="alert.resolve", resource_type="alert", actor_user_id=current_user.id, resource_id=alert.id)
    return alert
