"""Consented people + encrypted face templates.

Consent is a first-class server-side record: no consent, no enrolment,
no identification. Templates are AES-256-GCM encrypted at rest with the
biometric key; withdrawal hard-deletes every trace.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .user import utcnow


class Person(Base):
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))
    # ISO timestamp the owner typed their consent + sha256 of the statement
    consent_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consent_statement_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class FaceTemplate(Base):
    __tablename__ = "face_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("people.id", ondelete="CASCADE"), unique=True)
    # AES-GCM ciphertext token over JSON [float, ...] (512-d embedding)
    embedding_encrypted: Mapped[str] = mapped_column(Text)
    samples_count: Mapped[int] = mapped_column(Integer, default=0)
    quality: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow)
