"""Fixed-window rate limiting + login lockout (DB-backed, multi-process safe)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.rate import LoginFailure, RateCounter
from ..models.user import utcnow


def _window_start(now: datetime, window_seconds: int) -> datetime:
    epoch = int(now.timestamp()) // window_seconds * window_seconds
    return datetime.fromtimestamp(epoch, tz=now.tzinfo)


def bucket_ip(identifier: str, ip: str) -> str:
    """Stable, non-reversible bucket key (never stashes raw identifiers)."""
    return hashlib.sha256(f"{identifier}|{ip}".encode()).hexdigest()


async def hit(
    session: AsyncSession,
    bucket: str,
    *,
    limit: int,
    window_seconds: int,
) -> bool:
    """Count one hit; return False when the bucket is over its limit."""
    now = utcnow()
    start = _window_start(now, window_seconds)
    stmt = (
        sqlite_insert(RateCounter)
        .values(bucket=bucket, window_start=start, count=1)
        .on_conflict_do_update(
            index_elements=["bucket", "window_start"],
            set_={"count": RateCounter.__table__.c.count + 1},
        )
        .returning(RateCounter.count)
    )
    result = await session.execute(stmt)
    count = result.scalar_one()
    return count <= limit


async def count_hits(session: AsyncSession, bucket: str,
                     window_seconds: int) -> int:
    now = utcnow()
    earliest = now - timedelta(seconds=window_seconds)
    total = await session.scalar(
        select(func.coalesce(func.sum(RateCounter.count), 0)).where(
            RateCounter.bucket == bucket,
            RateCounter.window_start > earliest))
    return int(total or 0)


async def record_login_failure(
    session: AsyncSession,
    identifier: str,
    ip: str,
) -> None:
    session.add(LoginFailure(key=bucket_ip(identifier, ip)))
    await session.flush()


async def login_locked_out(
    session: AsyncSession,
    identifier: str,
    ip: str,
    *,
    max_failures: int,
    lockout_minutes: int,
) -> bool:
    """True after >= max_failures failures within the lockout window."""
    now = utcnow()
    earliest = now - timedelta(minutes=lockout_minutes)
    failures = await session.scalar(
        select(func.count(LoginFailure.id)).where(
            LoginFailure.key == bucket_ip(identifier, ip),
            LoginFailure.ts > earliest))
    return int(failures or 0) >= max_failures
