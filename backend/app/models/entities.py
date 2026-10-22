"""SQLAlchemy Entity Models matching the Surveillance Architecture Specification."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    """Application user accounts with role-based access control."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)  # active, locked, disabled
    role: Mapped[str] = mapped_column(String(32), default="viewer", nullable=False)  # owner, admin, operator, viewer
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    cameras: Mapped[list["Camera"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    mobile_devices: Mapped[list["MobileDevice"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Camera(Base):
    """Registered cameras (laptop webcams, RTSP streams, IP cameras, registered phones)."""
    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), default="webcam", nullable=False)  # webcam, rtsp, ip_camera, mobile
    connection_secret_ref: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    connection_secret_encrypted: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    location_label: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="online", nullable=False)  # online, offline, paused, error
    stream_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    # Health metrics
    fps: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    resolution: Mapped[str] = mapped_column(String(32), default="1280x720", nullable=False)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    owner: Mapped[User] = relationship(back_populates="cameras")
    events: Mapped[list["DetectionEvent"]] = relationship(back_populates="camera", cascade="all, delete-orphan")

    def set_secret(self, secret: str) -> None:
        from ..core.crypto import encrypt_string
        self.connection_secret_encrypted = encrypt_string(secret, aad=b"camera-credential")

    def get_decrypted_secret(self) -> Optional[str]:
        from ..core.crypto import decrypt_string
        if not self.connection_secret_encrypted:
            return None
        try:
            return decrypt_string(self.connection_secret_encrypted, aad=b"camera-credential")
        except Exception:
            return None


class MobileDevice(Base):
    """Authenticated mobile cameras (Android/iOS)."""
    __tablename__ = "mobile_devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    device_name: Mapped[str] = mapped_column(String(120), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), default="android", nullable=False)  # android, ios
    credential_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    device_token: Mapped[str] = mapped_column(String(256), unique=True, index=True, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped[User] = relationship(back_populates="mobile_devices")


class Person(Base):
    """Enrolled identities (Only consenting individuals are ever identified)."""
    __tablename__ = "people"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    # User-provided metadata (NOT inferred by computer vision!)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    role_relationship: Mapped[str] = mapped_column(String(64), default="resident", nullable=False)  # resident, employee, visitor, owner
    contact_details: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    photo_object_key: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="enrolled", nullable=False)  # enrolled, withdrawn, archived

    first_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    consent_records: Mapped[list["ConsentRecord"]] = relationship(back_populates="person", cascade="all, delete-orphan")
    face_templates: Mapped[list["FaceTemplate"]] = relationship(back_populates="person", cascade="all, delete-orphan")
    events: Mapped[list["DetectionEvent"]] = relationship(back_populates="person")

    def has_active_consent(self, db) -> bool:
        from datetime import datetime, timezone
        from sqlalchemy import select
        now = datetime.now(timezone.utc)
        stmt = select(ConsentRecord).where(
            ConsentRecord.person_id == self.id,
            ConsentRecord.withdrawn_at.is_(None),
            (ConsentRecord.expires_at.is_(None) | (ConsentRecord.expires_at > now)),
        )
        return db.scalars(stmt).first() is not None


class ConsentRecord(Base):
    """Explicit consent authorization records."""
    __tablename__ = "consent_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    person_id: Mapped[str] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), index=True, nullable=False)
    consent_scope: Mapped[str] = mapped_column(String(64), default="face_verification", nullable=False)
    notice_version: Mapped[str] = mapped_column(String(32), default="1.0", nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)

    person: Mapped[Person] = relationship(back_populates="consent_records")


class FaceTemplate(Base):
    """AES-256-GCM encrypted biometric template representation."""
    __tablename__ = "face_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    person_id: Mapped[str] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), index=True, nullable=False)
    template_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), default="facenet", nullable=False)
    embedding_dim: Mapped[int] = mapped_column(Integer, default=512, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    person: Mapped[Person] = relationship(back_populates="face_templates")


class DetectionEvent(Base):
    """Detection, motion, and tracking event history."""
    __tablename__ = "detection_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)  # person, motion, disconnect, alert

    # Anonymous track ID (e.g. TRK-042)
    track_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # CRITICAL PRIVACY RULE: person_id is nullable! Unknown people are NEVER assigned a fabricated profile.
    person_id: Mapped[Optional[str]] = mapped_column(ForeignKey("people.id", ondelete="SET NULL"), nullable=True, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    snapshot_object_key: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), default="unreviewed", nullable=False)  # unreviewed, confirmed, false_positive
    metadata_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)

    camera: Mapped[Camera] = relationship(back_populates="events")
    person: Mapped[Optional[Person]] = relationship(back_populates="events")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="event", cascade="all, delete-orphan")


class Alert(Base):
    """Actionable alert triggers and notifications."""
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    event_id: Mapped[str] = mapped_column(ForeignKey("detection_events.id", ondelete="CASCADE"), index=True, nullable=False)
    recipient_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    severity: Mapped[str] = mapped_column(String(32), default="medium", nullable=False)  # low, medium, high, critical
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)  # active, acknowledged, resolved
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    event: Mapped[DetectionEvent] = relationship(back_populates="alerts")


class AuditLog(Base):
    """Append-only audit trail for all access and modifications."""
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    actor_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), default="success", nullable=False)
    details_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class RetentionPolicy(Base):
    """Data retention rules."""
    __tablename__ = "retention_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)  # events, snapshots, audit_logs
    retention_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    deletion_mode: Mapped[str] = mapped_column(String(32), default="purge", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Conversation(Base):
    """User conversation session for persistent context."""
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), default="New Conversation", nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    user: Mapped[User] = relationship(back_populates="conversations")
    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="conversation", cascade="all, delete-orphan", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    """Individual turn in a conversation."""
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # user, assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    speech_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action_executed: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
