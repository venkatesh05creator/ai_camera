"""Camera registry, health, events, notifications, ingest nonces."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .user import utcnow


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(16))  # webcam | phone | rtsp
    source: Mapped[str] = mapped_column(String(500))  # index str or URL
    enabled: Mapped[bool] = mapped_column(default=True)
    retention_days: Mapped[int] = mapped_column(Integer, default=7)
    # ingest token: only the SHA-256 hash is stored; plaintext shown once
    token_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_cameras_kind", "kind"),)


class CameraHealth(Base):
    __tablename__ = "camera_health"

    camera_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cameras.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="starting")
    last_frame_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None)
    last_event_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None)
    fps: Mapped[float | None] = mapped_column(Float, default=None)
    frames: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String(300), default=None)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CameraEvent(Base):
    __tablename__ = "camera_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    kind: Mapped[str] = mapped_column(String(16))  # motion | person
    person_count: Mapped[int] = mapped_column(Integer, default=0)
    motion_score: Mapped[float] = mapped_column(Float, default=0.0)
    snapshot_encrypted: Mapped[str | None] = mapped_column(Text, default=None)
    snapshot_status: Mapped[str] = mapped_column(String(32), default="none")
    # encrypted JSON: {"known":[{"person_id": 3, "name": "Venki", "score"]:
    #                   ...}], "unknown_faces": 1}
    labels_encrypted: Mapped[str | None] = mapped_column(Text, default=None)

    __table_args__ = (Index("ix_camera_events_cam_ts", "camera_id", "ts"),)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    camera_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("cameras.id", ondelete="SET NULL"), default=None)
    kind: Mapped[str] = mapped_column(String(16))  # person | health
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(500))
    is_read: Mapped[bool] = mapped_column(default=False)

    __table_args__ = (Index("ix_notifications_unread", "is_read", "ts"),)


class IngestNonce(Base):
    """HMAC-ingest replay protection (one nonce per accepted frame)."""
    __tablename__ = "ingest_nonces"

    nonce: Mapped[str] = mapped_column(String(128), primary_key=True)
    camera_id: Mapped[int] = mapped_column(Integer, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_ingest_nonces_cam", "camera_id"),)
