"""Strict request/response schemas.

Every inbound payload is validated by a schema that forbids unknown fields,
whitespace trimming, explicit length limits and typed fields.  Client side
validation is only a usability feature; these schemas are the real gate.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import DeviceStatus, DeviceType, Role

_STRICT = ConfigDict(extra="forbid", str_strip_whitespace=True, protected_namespaces=())


class StrictModel(BaseModel):
    """Base class rejecting unknown fields."""

    model_config = _STRICT


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
class RegisterRequest(StrictModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)
    display_name: str = Field(default="", max_length=120)

    @field_validator("email")
    @classmethod
    def _lower(cls, value: str) -> str:
        return value.strip().lower()


class LoginRequest(StrictModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class MfaVerifyRequest(StrictModel):
    code: str = Field(min_length=6, max_length=12)


class ForgotPasswordRequest(StrictModel):
    email: str = Field(min_length=3, max_length=320)


class ResetPasswordRequest(StrictModel):
    token: str = Field(min_length=10, max_length=512)
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordRequest(StrictModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class ProfileUpdateRequest(StrictModel):
    display_name: str = Field(default="", max_length=120)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    email: str
    email_verified: bool
    role: str
    display_name: str
    mfa_enabled: bool
    created_at: datetime


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    user_agent: str


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------
class DeviceCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    device_type: DeviceType = DeviceType.WEBCAM
    location_label: str = Field(default="", max_length=160)
    stream_url: Optional[str] = Field(default=None, max_length=2048)

    @field_validator("name", "location_label")
    @classmethod
    def _no_control_chars(cls, value: str) -> str:
        if any(ord(ch) < 32 for ch in value):
            raise ValueError("must not contain control characters")
        return value


class DeviceUpdate(StrictModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    location_label: Optional[str] = Field(default=None, max_length=160)
    status: Optional[DeviceStatus] = None
    stream_url: Optional[str] = Field(default=None, max_length=2048)


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    name: str
    device_type: str
    status: str
    location_label: str
    has_stream_url: bool
    last_seen_at: Optional[datetime]
    created_at: datetime
    event_count: int = 0


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------
_EVENT_KINDS = {"motion", "person", "sound", "device_status", "note", "alert"}


class EventCreate(StrictModel):
    kind: str = Field(min_length=1, max_length=48)
    summary: str = Field(default="", max_length=400)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    occurred_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("kind")
    @classmethod
    def _known_kind(cls, value: str) -> str:
        if value not in _EVENT_KINDS:
            raise ValueError("unsupported event kind")
        return value


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    device_id: int
    device_name: str = ""
    kind: str
    summary: str
    confidence: float
    occurred_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Identities (biometric enrolment)
# ---------------------------------------------------------------------------
class IdentityEnroll(StrictModel):
    label: str = Field(min_length=1, max_length=120)
    consent: bool
    images: List[str] = Field(default_factory=list, max_length=5)

    @field_validator("images")
    @classmethod
    def _limit(cls, value: List[str]) -> List[str]:
        for item in value:
            if len(item) > 8 * 1024 * 1024:
                raise ValueError("image payload is too large")
        return value


class IdentityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    label: str
    model_name: str
    embedding_dim: int
    consent_at: datetime
    consent_version: str
    expires_at: Optional[datetime]
    withdrawn_at: Optional[datetime]
    created_at: datetime


# ---------------------------------------------------------------------------
# AI chat
# ---------------------------------------------------------------------------
class ChatRequest(StrictModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[int] = Field(default=None, ge=1)


class ChatResponse(BaseModel):
    conversation_id: int
    message_id: int
    reply: str
    tokens_used: int
    provider: str
    pending_actions: List[Dict[str, Any]] = Field(default_factory=list)


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    token_count: int


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    role: str
    content: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
class SearchHit(BaseModel):
    type: str
    id: int
    title: str
    snippet: str
    url: str


class SearchResponse(BaseModel):
    query: str
    total: int
    hits: List[SearchHit]


# ---------------------------------------------------------------------------
# Contact form
# ---------------------------------------------------------------------------
class ContactRequest(StrictModel):
    email: str = Field(min_length=3, max_length=320)
    subject: str = Field(min_length=3, max_length=160)
    message: str = Field(min_length=10, max_length=4000)
    website: str = Field(default="", max_length=200)  # honeypot - must stay empty


# ---------------------------------------------------------------------------
# Administration
# ---------------------------------------------------------------------------
class RoleUpdateRequest(StrictModel):
    role: Role

    @field_validator("role")
    @classmethod
    def _known(cls, value: Role) -> Role:
        return value


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    actor_user_id: Optional[int]
    action: str
    target_type: str
    target_id: str
    outcome: str
    created_at: datetime
    detail: Dict[str, Any] = Field(default_factory=dict)


class MessageOutPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    email: str
    subject: str
    message: str
    status: str
    created_at: datetime


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    limit: int
    offset: int


SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,120}$")
