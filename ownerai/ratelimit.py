"""Layered rate limiting backed by the database.

The counters live in the database so that every worker of a multi-process
deployment shares the same state.  A fixed window is used, which is accurate
enough for abuse prevention and cheap to maintain.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import RateLimitBucket
from .settings import Settings, get_settings

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Raised when a caller exceeds a configured limit."""

    def __init__(self, scope: str, limit: int, retry_after: int) -> None:
        super().__init__(f"rate limit exceeded for scope '{scope}'")
        self.scope = scope
        self.limit = limit
        self.retry_after = retry_after


@dataclass(frozen=True)
class RateLimitResult:
    """Outcome of a rate-limit check."""

    allowed: bool
    limit: int
    remaining: int
    retry_after: int


def _bucket_key(scope: str, identifier: str) -> str:
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:32]
    return f"{scope}:{digest}"


def check_rate_limit(
    db: Session,
    scope: str,
    identifier: str,
    limit: int,
    window_seconds: int,
    *,
    settings: Settings | None = None,
) -> RateLimitResult:
    """Consume one token for ``identifier`` within ``scope``.

    Raises :class:`RateLimitExceeded` when the limit is exhausted.
    """
    settings = settings or get_settings()
    if not settings.rate_limit_enabled:
        return RateLimitResult(allowed=True, limit=limit, remaining=limit, retry_after=0)

    now = datetime.now(timezone.utc)
    key = _bucket_key(scope, identifier)
    bucket = db.get(RateLimitBucket, key)
    if bucket is None:
        bucket = RateLimitBucket(bucket_key=key, scope=scope, window_start=now, count=0)
        db.add(bucket)
        try:
            db.flush()
        except IntegrityError:  # pragma: no cover - concurrent insert
            db.rollback()
            bucket = db.get(RateLimitBucket, key)
            if bucket is None:
                raise

    window_start = bucket.window_start
    if window_start.tzinfo is None:
        window_start = window_start.replace(tzinfo=timezone.utc)
    if (now - window_start) >= timedelta(seconds=window_seconds):
        bucket.window_start = now
        bucket.count = 0
        window_start = now

    if bucket.count >= limit:
        elapsed = (now - window_start).total_seconds()
        retry_after = max(1, int(window_seconds - elapsed))
        db.commit()
        raise RateLimitExceeded(scope=scope, limit=limit, retry_after=retry_after)

    bucket.count += 1
    bucket.updated_at = now
    db.commit()
    remaining = max(0, limit - bucket.count)
    return RateLimitResult(allowed=True, limit=limit, remaining=remaining, retry_after=0)


def purge_expired_buckets(db: Session, older_than_seconds: int = 86400) -> int:
    """Remove stale buckets; returns the number of deleted rows."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=older_than_seconds)
    result = db.execute(delete(RateLimitBucket).where(RateLimitBucket.updated_at < cutoff))
    db.commit()
    return int(result.rowcount or 0)
