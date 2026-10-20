"""Audit trail for privileged actions."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..models import AuditLog

logger = logging.getLogger(__name__)

#: Values that must never end up in the audit log.
_FORBIDDEN_KEYS = {
    "password",
    "new_password",
    "current_password",
    "token",
    "secret",
    "api_key",
    "csrf_token",
    "template",
    "embedding",
}


def redact_detail(detail: dict[str, Any]) -> dict[str, Any]:
    """Remove sensitive keys from an audit detail payload."""
    if not isinstance(detail, dict):
        return {}
    cleaned: dict[str, Any] = {}
    for key, value in detail.items():
        if key.lower() in _FORBIDDEN_KEYS:
            continue
        if isinstance(value, (int, float, bool)) or value is None:
            cleaned[key] = value
        elif isinstance(value, str):
            cleaned[key] = value[:200]
        else:
            cleaned[key] = str(value)[:200]
    return cleaned


def hash_ip(ip: str) -> str:
    """Store a one-way hash of an IP address instead of the address itself."""
    if not ip:
        return ""
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()


def record(
    db: Session,
    *,
    action: str,
    actor_user_id: Optional[int] = None,
    target_type: str = "",
    target_id: str = "",
    outcome: str = "success",
    ip: str = "",
    detail: Optional[dict[str, Any]] = None,
) -> AuditLog:
    """Append an entry to the audit log."""
    entry = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type[:48],
        target_id=str(target_id)[:64],
        outcome=outcome[:24],
        ip_hash=hash_ip(ip),
        detail_json=json.dumps(redact_detail(detail or {}), sort_keys=True),
    )
    db.add(entry)
    db.commit()
    logger.info(
        "audit",
        extra={
            "action": action,
            "actor_user_id": actor_user_id,
            "target_type": target_type,
            "target_id": str(target_id)[:64],
            "outcome": outcome,
        },
    )
    return entry
