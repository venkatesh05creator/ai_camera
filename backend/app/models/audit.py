"""Append-only, hash-chained audit log (tamper-evident).

Each entry embeds the SHA-256 of the previous entry in ``prev_hash`` and
stores its own ``entry_hash`` = sha256(canonical fields || prev_hash).
Verification recomputes the chain.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .user import utcnow


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    actor_user_id: Mapped[int | None] = mapped_column(Integer, default=None)
    action: Mapped[str] = mapped_column(String(64))
    target: Mapped[str] = mapped_column(String(200), default="")
    result: Mapped[str] = mapped_column(String(16), default="ok")  # ok|denied|error
    detail_json: Mapped[str] = mapped_column(Text, default="{}")

    prev_hash: Mapped[str] = mapped_column(String(64))
    entry_hash: Mapped[str] = mapped_column(String(64))
