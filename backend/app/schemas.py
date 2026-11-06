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
