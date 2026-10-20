"""Environment-driven configuration.

All tunables live here so that secrets never have to be committed.  Every
setting is read from the process environment (optionally from a local ``.env``
file) using the ``OWNERAI_`` prefix, for example ``OWNERAI_SECRET_KEY``.

The module performs *fail-safe* validation: in production a missing/weak
secret, disabled secure cookies or an empty allow-list of trusted hosts abort
the start-up instead of silently running an insecure deployment.
"""

from __future__ import annotations

import functools
import secrets
from typing import List, Literal, Optional, Union

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# A development-only placeholder.  It is rejected outside of development.
DEV_SECRET_KEY = "dev-insecure-secret-change-me"  # nosec B105

EnvName = Literal["development", "test", "production"]


class Settings(BaseSettings):
    """Validated application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="OWNERAI_",
        extra="ignore",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    app_name: str = "Owner-Only AI Camera Assistant"
    app_env: EnvName = "development"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"
    json_logs: bool = True

    # ------------------------------------------------------------------
    # Secrets (server side only - never sent to a browser)
    # ------------------------------------------------------------------
    secret_key: SecretStr = SecretStr("")
    biometric_encryption_key: Optional[SecretStr] = None
    ai_api_key: Optional[SecretStr] = None

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------
    database_url: str = "sqlite:///./var/ownerai.db"
    db_echo: bool = False
    sql_echo: bool = False

    # ------------------------------------------------------------------
    # Sessions / cookies
    # ------------------------------------------------------------------
    session_cookie_name: str = "ownerai_session"
    csrf_cookie_name: str = "ownerai_csrf"
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    session_idle_minutes: int = 30
    session_absolute_minutes: int = 720
    remember_me_days: int = 30
    password_min_length: int = 12
    password_max_length: int = 256

    # ------------------------------------------------------------------
    # Transport / proxy hardening
    # ------------------------------------------------------------------
    https_only: bool = False
    hsts_enabled: bool = False
    hsts_max_age: int = 31536000
    hsts_include_subdomains: bool = True
    trusted_hosts: Union[str, List[str]] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "testserver"]
    )
    cors_origins: Union[str, List[str]] = Field(default_factory=list)
    trust_proxy_headers: bool = False

    # ------------------------------------------------------------------
    # Rate limiting (per scope / key)
    # ------------------------------------------------------------------
    rate_limit_enabled: bool = True
    login_rate_limit: int = 5
    login_rate_window_seconds: int = 300
    register_rate_limit: int = 3
    register_rate_window_seconds: int = 3600
    password_reset_rate_limit: int = 3
    password_reset_rate_window_seconds: int = 3600
    api_rate_limit: int = 240
    api_rate_window_seconds: int = 60
    search_rate_limit: int = 30
    search_rate_window_seconds: int = 60
    ai_rate_limit: int = 20
    ai_rate_window_seconds: int = 60
    contact_rate_limit: int = 3
    contact_rate_window_seconds: int = 3600
    upload_rate_limit: int = 10
    upload_rate_window_seconds: int = 600

    # ------------------------------------------------------------------
    # Request limits
    # ------------------------------------------------------------------
    max_request_body_bytes: int = 8 * 1024 * 1024
    max_upload_bytes: int = 5 * 1024 * 1024
    max_page_size: int = 100
    default_page_size: int = 25

    # ------------------------------------------------------------------
    # Email / notifications
    # ------------------------------------------------------------------
    mailer_backend: Literal["console", "smtp", "null"] = "console"
    mailer_from: str = "no-reply@localhost"
    support_destination: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: Optional[SecretStr] = None
    smtp_use_tls: bool = True
    require_email_verification: bool = False
    email_token_ttl_minutes: int = 60

    # ------------------------------------------------------------------
    # Multi-factor authentication
    # ------------------------------------------------------------------
    mfa_required_for_admin: bool = True
    totp_issuer: str = "Owner-Only AI Camera Assistant"
    totp_step_seconds: int = 30
    totp_window: int = 1

    # ------------------------------------------------------------------
    # Biometrics
    # ------------------------------------------------------------------
    biometrics_enabled: bool = True
    biometric_retention_days: int = 90
    face_match_threshold: float = 0.72
    enrollment_max_images: int = 5

    # ------------------------------------------------------------------
    # Cameras / devices
    # ------------------------------------------------------------------
    allow_private_camera_hosts: Union[str, List[str]] = Field(default_factory=list)
    camera_fetch_timeout_seconds: float = 8.0
    camera_max_bytes: int = 4 * 1024 * 1024
    camera_max_redirects: int = 2
    device_token_ttl_seconds: int = 300

    # ------------------------------------------------------------------
    # AI provider
    # ------------------------------------------------------------------
    ai_provider: Literal["offline", "openai_compatible"] = "offline"
    ai_api_base: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4o-mini"
    ai_timeout_seconds: float = 30.0
    ai_max_output_tokens: int = 700
    ai_context_max_chars: int = 4000
    ai_daily_token_budget: int = 100_000
    ai_daily_request_budget: int = 200

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------
    @field_validator("trusted_hosts", "cors_origins", "allow_private_camera_hosts", mode="before")
    @classmethod
    def _split_csv(cls, value):  # noqa: D102
        if value is None:
            return []
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            if value.startswith("["):  # allow JSON-ish values from the environment
                import json

                try:
                    return json.loads(value)
                except ValueError:
                    pass
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("debug")
    @classmethod
    def _no_debug_in_production(cls, value: bool, info) -> bool:
        if value and info.data.get("app_env") == "production":
            raise ValueError("debug mode must be disabled in production")
        return value

    @model_validator(mode="after")
    def _validate_environment(self) -> "Settings":
        # Normalise the list-like settings so that consumers can always rely
        # on them being lists.
        self.trusted_hosts = self._split_csv(self.trusted_hosts)
        self.cors_origins = self._split_csv(self.cors_origins)
        self.allow_private_camera_hosts = self._split_csv(self.allow_private_camera_hosts)

        if self.app_env == "production":
            problems: List[str] = []
            if not self.secret_key.get_secret_value():
                problems.append("OWNERAI_SECRET_KEY must be set")
            elif self.secret_key.get_secret_value() == DEV_SECRET_KEY:
                problems.append("OWNERAI_SECRET_KEY must not use the development default")
            elif len(self.secret_key.get_secret_value()) < 32:
                problems.append("OWNERAI_SECRET_KEY must be at least 32 characters")
            if not self.https_only:
                problems.append("OWNERAI_HTTPS_ONLY must be true in production")
            if not self.hsts_enabled:
                problems.append("OWNERAI_HSTS_ENABLED must be true in production")
            if not self.trusted_hosts:
                problems.append("OWNERAI_TRUSTED_HOSTS must list the public host names")
            if self.cors_origins and "*" in self.cors_origins:
                problems.append("wildcard CORS origins are not allowed")
            if self.cookie_samesite == "none" and not self.https_only:
                problems.append("SameSite=None requires HTTPS")
            if problems:
                raise ValueError("insecure production configuration: " + "; ".join(problems))

        if self.session_idle_minutes <= 0 or self.session_absolute_minutes <= 0:
            raise ValueError("session lifetimes must be positive")
        if self.session_idle_minutes > self.session_absolute_minutes:
            raise ValueError("session idle timeout cannot exceed the absolute timeout")
        if self.password_min_length < 8:
            raise ValueError("password_min_length must be at least 8")
        if self.max_page_size < 1 or self.default_page_size < 1:
            raise ValueError("page sizes must be positive")
        if self.default_page_size > self.max_page_size:
            raise ValueError("default_page_size cannot exceed max_page_size")
        return self

    # ------------------------------------------------------------------
    # Derived helpers
    # ------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_testing(self) -> bool:
        return self.app_env == "test"

    @property
    def secure_cookies(self) -> bool:
        """Cookies are only marked ``Secure`` when the deployment is HTTPS."""
        return self.https_only or self.is_production

    def ensure_runtime_directories(self) -> None:
        """Create the local directories the application needs."""
        from pathlib import Path

        for raw_path in (self.database_url,):
            if not raw_path.startswith("sqlite"):
                continue
            db_path = raw_path.split("///", 1)[-1]
            if db_path and db_path != ":memory:":
                Path(db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()


def reset_settings_cache() -> None:
    """Clear the settings cache (used by the test-suite)."""
    get_settings.cache_clear()


def generate_secret(length: int = 48) -> str:
    """Generate a URL-safe random secret."""
    return secrets.token_urlsafe(length)
