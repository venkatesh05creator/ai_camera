"""Encrypted memory items (facts the owner teaches Aegis).

Text is AES-256-GCM encrypted at rest; the key derives from
OWNERAI_BIOMETRIC_ENCRYPTION_KEY (falling back to the app secret for
local-only installs). Rows are hard-deleted on request (no tombstones).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .user import utcnow


class MemoryItem(Base):
    __tablename__ = "memory_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32), default="fact")
    text_encrypted: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (Index("ix_memory_kind", "kind"),)
