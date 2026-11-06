"""API request/response schemas (strict: unknown fields rejected)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BootstrapIn(StrictModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=200)
    display_name: str = Field(min_length=1, max_length=120)


class LoginIn(StrictModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)
    remember_me: bool = False
    totp_code: str = Field(default="", max_length=10)


class MeOut(StrictModel):
    id: int
    email: str
    display_name: str
    role: str
    totp_enabled: bool


class StatusOut(StrictModel):
    needs_bootstrap: bool
    app_env: str
    panic_active: bool


class TotpSetupOut(StrictModel):
    provisioning_uri: str


class TotpIn(StrictModel):
    code: str = Field(min_length=6, max_length=10)


class PanicIn(StrictModel):
    reason: str = Field(default="", max_length=300)


class AuditVerifyOut(StrictModel):
    valid: bool
    entries: int
    first_broken_id: int | None
    problem: str | None


# --- Phase 3: AI brain + memory ---------------------------------------------

class ChatMessageIn(StrictModel):
    role: str = Field(default="user", pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class ChatIn(StrictModel):
    messages: list[ChatMessageIn] = Field(min_length=1, max_length=20)
    allow_remote: bool = False
    # optional single-question shortcut (multi-turn = pass history above)
    question: str = Field(default="", max_length=2000)


class MemoryIn(StrictModel):
    kind: str = Field(default="fact", max_length=32)
    text: str = Field(min_length=1, max_length=2000)


class MemoryOut(StrictModel):
    id: int
    kind: str
    text: str
    created_at: str
    updated_at: str


# --- Phase 4: cameras --------------------------------------------------------

class CameraIn(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = Field(pattern="^(webcam|phone|rtsp)$")
    source: str = Field(min_length=1, max_length=500)


class CameraUpdateIn(StrictModel):
    enabled: bool | None = None
    name: str | None = Field(default=None, max_length=120)
    retention_days: int | None = Field(default=None, ge=1, le=90)


class CameraOut(StrictModel):
    id: int
    name: str
    kind: str
    source: str
    enabled: bool
    retention_days: int
    running: bool = False
    health: dict = {}
