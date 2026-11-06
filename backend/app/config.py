"""Typed settings for Aegis AI.

All configuration comes from the environment with the ``OWNERAI_`` prefix
(or a ``.env`` file in the project root, loaded tolerantly:
inline comments, stray spaces and quotes are stripped).

Production fail-safe: :meth:`Settings.production_problems` returns human
readable problems; the app **refuses to start** in production while that
list is non-empty (see ``main.create_app``).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


def load_env_file(path: Path = ENV_FILE) -> None:
    """Tolerant .env loader (sets values only if not already in the env)."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.split(" #")[0].strip().strip('"').strip("'")
        if key and value and key not in os.environ:  # empty values = unset
            os.environ[key] = value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OWNERAI_", extra="ignore")

    # app identity / runtime -------------------------------------------------
    app_name: str = "Aegis AI"
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    json_logs: bool = True

    # database ---------------------------------------------------------------
    database_url: str = "sqlite+aiosqlite:///./var/aegis.db"

    # crypto / sessions ------------------------------------------------------
    secret_key: SecretStr = SecretStr("")  # never a default in production
    session_idle_minutes: int = 30
    session_absolute_minutes: int = 720
    remember_me_hours: int = 168
    cookie_session_name: str = "aegis_session"
    cookie_csrf_name: str = "aegis_csrf"
    cookie_samesite: Literal["lax", "strict"] = "lax"

    # network ----------------------------------------------------------------
    host: str = "127.0.0.1"
    port: int = 8000
    https_only: bool = False
    hsts_enabled: bool = True
    hsts_max_age_seconds: int = 168 * 3600
    trusted_hosts: Annotated[list[str], NoDecode] = ["localhost", "127.0.0.1"]
    cors_origins: Annotated[list[str], NoDecode] = []  # empty = same-origin only; never "*"

    @field_validator("trusted_hosts", "cors_origins", mode="before")
    @classmethod
    def _tolerant_list(cls, value: object) -> object:
        """Accept 'a, b', JSON arrays, or single values for list fields."""
        if isinstance(value, str):
            cleaned = value.strip().strip("[] ").replace('"', "").replace("'", "")
            return [item.strip() for item in cleaned.split(",") if item.strip()]
        return value
    trust_proxy_headers: bool = False

    # rate limiting ----------------------------------------------------------
    rate_limit_enabled: bool = True
    login_rate_limit: int = 5
    login_rate_window_seconds: int = 60
    login_lockout_minutes: int = 15
    api_rate_limit: int = 120
    api_rate_window_seconds: int = 60

    # request limits ---------------------------------------------------------
    max_request_body_bytes: int = 1_000_000

    # camera / SSRF (used by later phases, validated here) --------------------
    allow_private_camera_hosts: bool = False
    camera_fetch_timeout_seconds: float = 10.0
    camera_max_bytes: int = 8_000_000
    camera_max_redirects: int = 3

    # crypto keys (later phases reuse these env names) ------------------------
    biometric_encryption_key: SecretStr = SecretStr("")

    # LLM (Phase 3: AI brain, local-first) ------------------------------------
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.1:8b"
    llm_default_provider: str = "ollama"
    chat_max_tokens: int = 2048
    chat_temperature: float = 0.0  # factual steps: deterministic by default
    chat_timeout_seconds: float = 120.0
    groq_api_key: SecretStr = SecretStr("")
    gemini_api_key: SecretStr = SecretStr("")
    openrouter_api_key: SecretStr = SecretStr("")
    nvidia_api_key: SecretStr = SecretStr("")

    # face recognition (Phase 5: People, consent-enrolled only) ----------------
    face_model_dir: str = "./models/insightface"
    face_model_name: str = "buffalo_sc"
    face_match_threshold: float = 0.35  # cosine similarity; below = unknown
    face_min_enrol_samples: int = 3

    @model_validator(mode="after")
    def _normalize_db_url(self) -> Settings:
        if self.database_url.startswith("sqlite:///") and "aiosqlite" not in self.database_url:
            object.__setattr__(self, "database_url", self.database_url.replace(
                "sqlite:///", "sqlite+aiosqlite:///", 1))
        return self

    # ---- production fail-safe ------------------------------------------------
    def production_problems(self) -> list[str]:
        problems: list[str] = []
        key = self.secret_key.get_secret_value()
        if not key:
            problems.append("OWNERAI_SECRET_KEY is required")
        elif len(key) < 32:
            problems.append("OWNERAI_SECRET_KEY is too short (min 32 chars)")
        if not self.https_only and self.trust_proxy_headers is False:
            problems.append("OWNERAI_HTTPS_ONLY=true is required in production "
                            "(or OWNERAI_TRUST_PROXY_HEADERS behind a TLS-terminating proxy)")
        if not self.trusted_hosts:
            problems.append("OWNERAI_TRUSTED_HOSTS must list allowed hosts in production")
        if "*" in self.cors_origins:
            problems.append("CORS wildcard '*' is never allowed")
        if not self.biometric_encryption_key.get_secret_value():
            problems.append("OWNERAI_BIOMETRIC_ENCRYPTION_KEY is required in production")
        return problems


def get_settings() -> Settings:
    load_env_file()
    return Settings()
