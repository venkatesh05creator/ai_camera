"""Audit logs explorer router."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import PERM_AUDIT_READ, has_permission
from ...models.entities import AuditLog, User
from ...schemas.schemas import AuditLogOut
from .auth import get_current_user

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=List[AuditLogOut])
def get_audit_logs(
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not has_permission(current_user.role, PERM_AUDIT_READ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to security audit logs requires owner or admin privileges",
        )
    stmt = select(AuditLog).order_by(desc(AuditLog.timestamp)).limit(limit)
    logs = db.scalars(stmt).all()
    return [AuditLogOut.model_validate(log) for log in logs]
