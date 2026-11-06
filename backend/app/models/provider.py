"""Provider usage + quota meter (honest counts, persisted)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ProviderUsage(Base):
    __tablename__ = "provider_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(120))
    day: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD (UTC)

    requests: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int | None] = mapped_column(Integer, default=None)
    output_tokens: Mapped[int | None] = mapped_column(Integer, default=None)
    errors: Mapped[int] = mapped_column(Integer, default=0)

    # set when a provider returns 429/rate-limit: skip until this time (UTC)
    cooldown_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None)

    __table_args__ = (
        UniqueConstraint("provider", "model", "day", name="uq_usage_pmd"),
        Index("ix_usage_provider_day", "provider", "day"),
    )
