"""Application settings and configuration."""

from __future__ import annotations

import functools
from pathlib import Path
from typing import List, Literal, Optional, Union

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Full-Stack AI Surveillance Platform Settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SURVEILLANCE_",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "AI Surveillance Platform"
    app_env: Literal["development", "test", "production"] = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # Secrets
    secret_key: SecretStr = SecretStr("insecure-dev-secret-key-at-least-32-chars-long")
    biometric_encryption_key: SecretStr = SecretStr("insecure-biometric-key-at-least-32-chars-long")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 120

    # Database
    database_url: str = "sqlite:///./var/surveillance.db"
    redis_url: Optional[str] = None

    # Storage paths
    media_storage_path: Path = Path("./var/media")
    snapshot_storage_path: Path = Path("./var/snapshots")

    # Security & CORS
    cors_origins: Union[str, List[str]] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:8000", "http://127.0.0.1:5173"])
    trusted_hosts: Union[str, List[str]] = Field(default_factory=lambda: ["*"])

    # Vision & Inference
    active_model: str = "facenet"
    face_match_threshold: float = 0.55
    person_detection_confidence: float = 0.45
    motion_sensitivity_threshold: int = 25
    motion_min_area: int = 500

    # Retention Defaults
    default_event_retention_days: int = 30
    unreviewed_snapshot_retention_days: int = 7

    @field_validator("cors_origins", "trusted_hosts", mode="before")
    @classmethod
    def _split_csv(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def _validate_production_security(self) -> "Settings":
        if self.app_env == "production":
            problems: List[str] = []
            sec_val = self.secret_key.get_secret_value()
            if not sec_val or sec_val == "insecure-dev-secret-key-at-least-32-chars-long" or len(sec_val) < 32:
                problems.append("SURVEILLANCE_SECRET_KEY must be configured with at least 32 characters in production")

            bio_val = self.biometric_encryption_key.get_secret_value()
            if not bio_val or bio_val == "insecure-biometric-key-at-least-32-chars-long" or len(bio_val) < 32:
                problems.append("SURVEILLANCE_BIOMETRIC_ENCRYPTION_KEY must be configured with at least 32 characters in production")

            cors = self.cors_origins if isinstance(self.cors_origins, list) else [self.cors_origins]
            if "*" in cors:
                problems.append("Wildcard CORS origins ('*') are prohibited in production")

            hosts = self.trusted_hosts if isinstance(self.trusted_hosts, list) else [self.trusted_hosts]
            if "*" in hosts:
                problems.append("Wildcard trusted hosts ('*') are prohibited in production")

            if problems:
                raise ValueError("Insecure production configuration: " + "; ".join(problems))
        return self

    def ensure_directories(self) -> None:
        """Create necessary media and database storage folders."""
        self.media_storage_path.mkdir(parents=True, exist_ok=True)
        self.snapshot_storage_path.mkdir(parents=True, exist_ok=True)
        if self.database_url.startswith("sqlite"):
            db_path = self.database_url.split("///")[-1]
            if db_path != ":memory:":
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.ensure_directories()
    return s
