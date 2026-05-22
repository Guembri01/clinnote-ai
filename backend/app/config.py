from __future__ import annotations
"""
ClinNote AI — Application Configuration
========================================
Loads all settings from environment variables / .env file using pydantic-settings.
HIPAA Note: No PHI should ever appear in configuration values.
"""


from functools import lru_cache
from typing import List

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration for ClinNote AI backend.
    All secrets must be provided via environment variables or .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Database
    # ------------------------------------------------------------------ #
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/clinnote_ai"

    # ------------------------------------------------------------------ #
    # Redis / Celery
    # ------------------------------------------------------------------ #
    REDIS_URL: str = "redis://localhost:6379/0"

    # ------------------------------------------------------------------ #
    # JWT / Auth
    # ------------------------------------------------------------------ #
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ------------------------------------------------------------------ #
    # PHI Encryption (AES-256 via Fernet)
    # ------------------------------------------------------------------ #
    ENCRYPTION_KEY: str = ""  # 32-byte URL-safe base64 Fernet key

    # ------------------------------------------------------------------ #
    # OpenAI — SOAP note generation
    # ------------------------------------------------------------------ #
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4.1-nano-2025-04-14"

    # ------------------------------------------------------------------ #
    # DeepInfra Whisper v3 — Transcription
    # ------------------------------------------------------------------ #
    DEEPINFRA_API_KEY: str = ""
    DEEPINFRA_WHISPER_ENDPOINT: str = (
        "https://api.deepinfra.com/v1/inference/openai/audio/transcriptions"
    )
    DEEPINFRA_WHISPER_MODEL: str = "openai/whisper-large-v3"

    # ------------------------------------------------------------------ #
    # Azure Document Intelligence — OCR
    # ------------------------------------------------------------------ #
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: str = (
        "https://bilelapi.cognitiveservices.azure.com/"
    )
    AZURE_DOCUMENT_INTELLIGENCE_KEY: str = ""

    # ------------------------------------------------------------------ #
    # Session / Recording limits (HIPAA FR-09)
    # ------------------------------------------------------------------ #
    SESSION_INACTIVITY_TIMEOUT: int = 900   # 15 minutes in seconds
    RECORDING_MAX_DURATION: int = 7200       # 120 minutes in seconds
    NOTE_EXPIRY_HOURS: int = 24              # Unapproved note auto-expiry

    # ------------------------------------------------------------------ #
    # CORS
    # ------------------------------------------------------------------ #
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://localhost:3001"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    # ------------------------------------------------------------------ #
    # App
    # ------------------------------------------------------------------ #
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # ------------------------------------------------------------------ #
    # MFA
    # ------------------------------------------------------------------ #
    TOTP_LOCKOUT_ATTEMPTS: int = 5
    TOTP_LOCKOUT_MINUTES: int = 5

    # ------------------------------------------------------------------ #
    # Rate limiting
    # ------------------------------------------------------------------ #
    AUTH_RATE_LIMIT: str = "5/minute"
    RATE_LIMIT_PER_MINUTE: int = 60
    LOGIN_RATE_LIMIT: str = "5/minute"
    MFA_RATE_LIMIT: str = "5/minute"

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        weak = {"change-me-in-production", "change-me-before-production", "secret", ""}
        if v.lower() in weak or len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 chars and not a known weak default")
        return v

    @field_validator("ENCRYPTION_KEY", mode="before")
    @classmethod
    def _check_encryption_key(cls, v: str) -> str:
        # Allow empty for test environments; warn otherwise.
        # Production-strict validation happens in the model_validator below
        # (which has access to ENVIRONMENT).
        return v

    @model_validator(mode="after")
    def _validate_encryption_key_for_environment(self) -> "Settings":
        """
        Production guard: ENCRYPTION_KEY must be set and 44 chars (Fernet
        URL-safe base64 32-byte key length) when running in production.
        """
        if self.ENVIRONMENT.lower() in ("production", "prod"):
            if not self.ENCRYPTION_KEY:
                raise ValueError(
                    "ENCRYPTION_KEY must be set in production "
                    "(44-char URL-safe base64 Fernet key required)"
                )
            if len(self.ENCRYPTION_KEY) != 44:
                raise ValueError(
                    "ENCRYPTION_KEY must be 44 chars (URL-safe base64 Fernet key); "
                    f"got {len(self.ENCRYPTION_KEY)} chars"
                )
        return self

    @model_validator(mode="after")
    def _validate_keys_differ(self) -> "Settings":
        """SECRET_KEY (JWT signing) must never equal ENCRYPTION_KEY (PHI at rest)."""
        if self.ENCRYPTION_KEY and self.SECRET_KEY == self.ENCRYPTION_KEY:
            raise ValueError(
                "SECRET_KEY and ENCRYPTION_KEY must be distinct values "
                "(JWT signing key must not equal PHI encryption key)"
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance (created once on first call)."""
    return Settings()
