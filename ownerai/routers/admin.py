"""Administrative endpoints.

Every action is audited, requires an explicit permission and - for role
changes - a fresh authentication.  An administrator can never grant the owner
role and nobody can change their own role.
"""

from __future__ import annotations

import json
import logging
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import authenticated_user, enforce_csrf
from ..models import AuditLog, ContactMessage, Role, User
from ..rbac import ADMIN_AUDIT, ADMIN_CONTACTS, ADMIN_ROLES, ADMIN_USERS, assignable_roles_for
from ..schemas import AuditOut, RoleUpdateRequest, UserOut
from ..services import audit
from ..sessions import revoke_all_sessions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=List[UserOut])
def list_users(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> List[UserOut]:
    """List the accounts of the installation."""
    _require(user, ADMIN_USERS)
    users = db.scalars(select(User).order_by(User.id).limit(limit).offset(offset)).all()
    return [UserOut.model_validate(item) for item in users]


@router.patch("/users/{target_id}/role", response_model=UserOut, dependencies=[Depends(enforce_csrf)])
def update_role(
    target_id: int,
    payload: RoleUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> UserOut:
    """Change the role of an account.

    Rules enforced on the server:

    * only the owner may grant or revoke the owner role,
    * an administrator may not assign a role above their own,
    * nobody may change their own role (no self escalation),
    * every change is audited and revokes the target's sessions.
    """
    _require(user, ADMIN_ROLES)
    target = db.get(User, target_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    if target.id == user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="you cannot change your own role",
        )
    new_role = payload.role.value
    allowed = assignable_roles_for(user.role)
    if new_role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="you are not allowed to assign this role",
        )
    if target.role == Role.OWNER.value and user.role != Role.OWNER.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")

    previous = target.role
    target.role = new_role
    db.commit()
    revoke_all_sessions(db, target)
    db.refresh(target)
    audit.record(
        db,
        action="admin.role_change",
        actor_user_id=user.id,
        target_type="user",
        target_id=target.id,
        ip=_client_ip(request),
        detail={"from": previous, "to": new_role},
    )
    return UserOut.model_validate(target)


@router.post("/users/{target_id}/status", dependencies=[Depends(enforce_csrf)])
def set_user_status(
    target_id: int,
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, bool]:
    """Enable or disable an account."""
    _require(user, ADMIN_USERS)
    target = db.get(User, target_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    if target.id == user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="you cannot disable yourself")
    active = bool((payload or {}).get("active", True))
    target.is_active = active
    db.commit()
    if not active:
        revoke_all_sessions(db, target)
    audit.record(
        db,
        action="admin.user_status",
        actor_user_id=user.id,
        target_type="user",
        target_id=target.id,
        ip=_client_ip(request),
        detail={"active": active},
    )
    return {"ok": True}


@router.get("/audit", response_model=List[AuditOut])
def list_audit(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> List[AuditOut]:
    """Return the audit trail."""
    _require(user, ADMIN_AUDIT)
    entries = db.scalars(
        select(AuditLog).order_by(AuditLog.id.desc()).limit(limit).offset(offset)
    ).all()
    results = []
    for entry in entries:
        try:
            detail = json.loads(entry.detail_json or "{}")
        except ValueError:  # pragma: no cover - defensive
            detail = {}
        results.append(
            AuditOut(
                id=entry.id,
                actor_user_id=entry.actor_user_id,
                action=entry.action,
                target_type=entry.target_type,
                target_id=entry.target_id,
                outcome=entry.outcome,
                created_at=entry.created_at,
                detail=detail if isinstance(detail, dict) else {},
            )
        )
    return results


@router.get("/contacts", response_model=List[dict])
def list_contacts(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> List[dict]:
    """Return the messages submitted through the public contact form."""
    _require(user, ADMIN_CONTACTS)
    from ..crypto import decrypt_bytes

    messages = db.scalars(
        select(ContactMessage).order_by(ContactMessage.id.desc()).limit(limit).offset(offset)
    ).all()
    results = []
    for message in messages:
        try:
            email = decrypt_bytes(message.email_ciphertext, aad=b"contact-email").decode("utf-8")
        except Exception:  # pragma: no cover - defensive
            email = ""
        results.append(
            {
                "id": message.id,
                "email": email,
                "subject": message.subject,
                "message": message.body,
                "status": message.status,
                "created_at": message.created_at.isoformat(),
            }
        )
    return results


@router.patch("/contacts/{message_id}", dependencies=[Depends(enforce_csrf)])
def update_contact(
    message_id: int,
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, bool]:
    """Mark a contact message as handled."""
    _require(user, ADMIN_CONTACTS)
    message = db.get(ContactMessage, message_id)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    new_status = str((payload or {}).get("status", "handled"))[:24]
    if new_status not in {"new", "handled", "spam", "closed"}:
        raise HTTPException(status_code=422, detail="invalid status")
    message.status = new_status
    db.commit()
    audit.record(
        db,
        action="admin.contact_status",
        actor_user_id=user.id,
        target_type="contact_message",
        target_id=message.id,
        ip=_client_ip(request),
        detail={"status": new_status},
    )
    return {"ok": True}


@router.get("/stats")
def stats(db: Session = Depends(get_db), user: User = Depends(authenticated_user)) -> dict[str, int]:
    """Return a few operational counters."""
    _require(user, ADMIN_AUDIT)
    users = db.scalar(select(func.count(User.id)))
    contacts = db.scalar(select(func.count(ContactMessage.id)))
    return {"users": int(users or 0), "contacts": int(contacts or 0)}


def _require(user: User, permission: str) -> None:
    from ..rbac import has_permission

    if not has_permission(user.role, permission):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")


def _client_ip(request: Request) -> str:
    from ..middleware import client_ip as resolve_ip

    return resolve_ip(request)
