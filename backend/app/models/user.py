"""User accounts. First account created is the owner; roles are hierarchical."""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def utcnow() -> datetime:
    # SQLite stores no timezone info; keep every timestamp naive UTC so
    # Python-side and SQL-side comparisons are consistent.
    return datetime.now(UTC).replace(tzinfo=None)


class Role(enum.StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    TRUSTED = "trusted"
    VIEWER = "viewer"

    @classmethod
    def rank(cls, role: Role) -> int:
        return {cls.OWNER: 4, cls.ADMIN: 3, cls.TRUSTED: 2, cls.VIEWER: 1}[role]

    def at_least(self, minimum: Role) -> bool:
        return Role.rank(self) >= Role.rank(minimum)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default=Role.VIEWER.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # TOTP 2FA (secret stored encrypted at the application layer)
    totp_secret_encrypted: Mapped[str] = mapped_column(String(300), default="")
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_users_role", "role"),)
