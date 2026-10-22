"""Pydantic schemas for request validation and API responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------------------------------------------------------------------------
# Auth & Users
# ---------------------------------------------------------------------------
class UserRegister(BaseModel):
    email: str = Field(min_length=3, max_length=256)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=120)
    role: Optional[str] = "operator"


class UserLogin(BaseModel):
    email: str = Field(min_length=3, max_length=256)
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str
    status: str
    role: str
    mfa_enabled: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------------------------------------------------------------------------
# Cameras
# ---------------------------------------------------------------------------
class CameraRegister(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    source_type: str = "webcam"  # webcam, rtsp, ip_camera, mobile
    location_label: str = Field(default="", max_length=160)
    stream_url: Optional[str] = None
    connection_secret: Optional[str] = None


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    location_label: Optional[str] = None
    status: Optional[str] = None
    stream_url: Optional[str] = None


class CameraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    source_type: str
    location_label: str
    status: str
    stream_url: Optional[str] = None
    fps: float
    resolution: str
    last_seen_at: Optional[datetime] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# People & Consent
# ---------------------------------------------------------------------------
class PersonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    age: Optional[int] = None
    gender: Optional[str] = None
    role_relationship: str = "resident"
    contact_details: Optional[str] = None
    notes: Optional[str] = None
    photo_base64: Optional[str] = None


class PersonUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    role_relationship: Optional[str] = None
    contact_details: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class ConsentGrant(BaseModel):
    consent_scope: str = "face_verification"
    notice_version: str = "1.0"
    confirm_explicit_consent: bool = Field(..., description="Must explicitly agree to biometrics")


class ConsentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    person_id: str
    consent_scope: str
    notice_version: str
    granted_at: datetime
    expires_at: Optional[datetime] = None
    withdrawn_at: Optional[datetime] = None


class PersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    role_relationship: str
    contact_details: Optional[str] = None
    notes: Optional[str] = None
    photo_object_key: Optional[str] = None
    status: str
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    consent_active: bool = False
    templates_count: int = 0


# ---------------------------------------------------------------------------
# Events & Alerts
# ---------------------------------------------------------------------------
class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    camera_id: str
    camera_name: Optional[str] = None
    occurred_at: datetime
    event_type: str
    track_id: Optional[str] = None
    person_id: Optional[str] = None
    person_name: Optional[str] = None
    confidence: float
    snapshot_url: Optional[str] = None
    review_status: str
    metadata_json: str


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: str
    severity: str
    status: str
    title: str
    description: str
    created_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    actor_user_id: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    ip_address: str
    outcome: str
    details_json: str
    timestamp: datetime


# ---------------------------------------------------------------------------
# Analytics & Reports
# ---------------------------------------------------------------------------
class ReportSummary(BaseModel):
    total_events: int
    total_persons_detected: int
    total_verified_matches: int
    total_motion_events: int
    active_cameras_count: int
    total_enrolled_profiles: int
    events_by_camera: Dict[str, int]
    events_by_type: Dict[str, int]
    avg_alert_response_seconds: float


# ---------------------------------------------------------------------------
# Conversations & Persistent Chat Memory
# ---------------------------------------------------------------------------
class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    content: str
    speech_text: Optional[str] = None
    action_executed: Optional[str] = None
    created_at: datetime


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    summary: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class ConversationCreate(BaseModel):
    title: Optional[str] = Field(default="New Conversation", max_length=200)


class ConversationImportRequest(BaseModel):
    title: Optional[str] = Field(default="Imported Conversation", max_length=200)
    messages: List[Dict[str, Any]] = Field(..., description="Array of turns with role and content")

