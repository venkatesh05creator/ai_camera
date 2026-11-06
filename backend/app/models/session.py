"""Server-side sessions with rotation and idle/absolute expiry.

Cookie content is ``<session_id>.<secret>``; the secret is stored only as a
SHA-256 hash. Rotation revokes the old row and issues a fresh secret.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .user import utcnow


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # uuid4().hex
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    secret_hash: Mapped[str] = mapped_column(String(64))  # sha256 hex

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow)
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    rotated_from: Mapped[str | None] = mapped_column(String(32), default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # request context captured at creation (audit/utility; never logged raw)
    ip: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(300), default="")

    # CSRF token bound to this session (double submit)
    csrf_token: Mapped[str] = mapped_column(String(64), default="")

    __table_args__ = (Index("ix_sessions_user_seen", "user_id", "last_seen_at"),)
