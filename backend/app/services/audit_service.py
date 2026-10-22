"""Append-only audit trail service."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from ..models.entities import AuditLog


def log_action(
    db: Session,
    action: str,
    resource_type: str,
    actor_user_id: Optional[str] = None,
    resource_id: Optional[str] = None,
    ip_address: str = "127.0.0.1",
    outcome: str = "success",
    details: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """Record an immutable security audit event."""
    log = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        outcome=outcome,
        details_json=json.dumps(details or {}),
        timestamp=datetime.now(timezone.utc),
    )
    db.add(log)
    db.commit()
    return log
