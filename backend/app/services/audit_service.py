"""Append-only, hash-chained audit trail.

Write path: compute ``entry_hash = sha256(prev_hash | canonical_fields)``
where ``prev_hash`` is the previous entry's hash (genesis = 64 zeros).
Verification: walk the chain, recompute, fail closed on any mismatch or gap.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.audit import AuditLog
from ..models.user import utcnow

GENESIS_HASH = "0" * 64


def canonical_entry(
    ts: datetime, action: str, target: str, result: str,
    detail_json: str, prev_hash: str,
) -> str:
    ts_text = ts.isoformat()
    return f"{ts_text}|{action}|{target}|{result}|{detail_json}|{prev_hash}"


def entry_digest(canonical_text: str) -> str:
    return hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()


async def record(
    session: AsyncSession,
    action: str,
    *,
    actor_user_id: int | None = None,
    target: str = "",
    result: str = "ok",
    detail: Mapping[str, Any] | None = None,
) -> AuditLog:
    """Append one entry; caller owns the transaction (commit)."""
    last = (await session.execute(
        select(AuditLog).order_by(AuditLog.id.desc()).limit(1))).scalar_one_or_none()
    prev_hash = last.entry_hash if last else GENESIS_HASH
    ts = utcnow()
    detail_json = json.dumps(dict(detail or {}), sort_keys=True, ensure_ascii=False)
    entry_hash = entry_digest(canonical_entry(
        ts, action, target, result, detail_json, prev_hash))
    entry = AuditLog(
        ts=ts, actor_user_id=actor_user_id, action=action,
        target=target, result=result, detail_json=detail_json,
        prev_hash=prev_hash, entry_hash=entry_hash,
    )
    session.add(entry)
    await session.flush()
    return entry


async def verify_chain(session: AsyncSession) -> dict[str, Any]:
    """Recompute the full chain. Report is factual, never fabricates success."""
    rows = (await session.execute(
        select(AuditLog).order_by(AuditLog.id.asc()))).scalars().all()
    expected_prev = GENESIS_HASH
    for row in rows:
        expected = entry_digest(canonical_entry(
            row.ts, row.action, row.target, row.result,
            row.detail_json, expected_prev))
        if row.prev_hash != expected_prev:
            return {"valid": False, "entries": len(rows),
                    "first_broken_id": row.id,
                    "problem": f"entry {row.id}: prev_hash does not link"}
        if row.entry_hash != expected:
            return {"valid": False, "entries": len(rows),
                    "first_broken_id": row.id,
                    "problem": f"entry {row.id}: entry_hash mismatch (tampered)"}
        expected_prev = row.entry_hash
    return {"valid": True, "entries": len(rows), "first_broken_id": None,
            "problem": None}


async def list_today(session: AsyncSession) -> list[AuditLog]:
    """Today's (UTC) audit entries, oldest first — used as chat evidence."""
    from datetime import datetime

    midnight = datetime.now(UTC).replace(
        hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=None)
    rows = (await session.execute(
        select(AuditLog).where(AuditLog.ts >= midnight)
        .order_by(AuditLog.id.asc()))).scalars().all()
    return list(rows)
