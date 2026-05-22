from __future__ import annotations
"""
ClinNote AI — Auth Schemas
============================
Pydantic models for authentication request/response payloads.
"""


from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    """Credentials submitted to the login endpoint."""

    email: EmailStr = Field(..., description="Clinician email address")
    password: str = Field(..., min_length=8, description="Account password")

    model_config = {"json_schema_extra": {"example": {"email": "dr.smith@hospital.org", "password": "SecurePass!1"}}}


class MFAVerifyRequest(BaseModel):
    """6-digit TOTP code submitted after initial password authentication."""

    token: str = Field(..., description="Temporary auth token from login step")
    totp_code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$", description="6-digit TOTP code from authenticator app")

    model_config = {"json_schema_extra": {"example": {"token": "eyJ...", "totp_code": "123456"}}}


class TokenResponse(BaseModel):
    """JWT token pair returned on successful authentication."""

    access_token: str = Field(..., description="Short-lived JWT access token (15 min)")
    refresh_token: str = Field(..., description="Long-lived JWT refresh token (7 days)")
    token_type: str = Field(default="bearer")
    expires_in: int = Field(..., description="Access token TTL in seconds")
    requires_mfa: bool = Field(default=False, description="True if MFA step required")

    model_config = {"json_schema_extra": {"example": {
        "access_token": "eyJ...",
        "refresh_token": "eyJ...",
        "token_type": "bearer",
        "expires_in": 900,
        "requires_mfa": False,
    }}}


class RefreshTokenRequest(BaseModel):
    """Payload to exchange a refresh token for a new access token."""

    refresh_token: str = Field(..., description="Valid JWT refresh token")


class RegisterRequest(BaseModel):
    """
    New clinician account registration.
    Admin-only endpoint — users cannot self-register.
    """

    email: EmailStr
    password: str = Field(..., min_length=12, description="Must be >= 12 chars with mixed case, digit, and symbol")
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(default="viewer")
    specialty: str | None = None
    npi_number: str | None = Field(default=None, max_length=20)
    org_id: str | None = None

    @field_validator("password")
    @classmethod
    def _strong_password(cls, v: str) -> str:
        """
        Enforce HIPAA-grade password complexity:
        - minimum 12 characters
        - at least 1 uppercase letter
        - at least 1 lowercase letter
        - at least 1 digit
        - at least 1 special character
        Raises a single ValueError listing ALL missing requirements.
        """
        import re

        special_chars = r"!@#$%^&*()_+\-=\[\]{};:'\"\\|,.<>/?`~"
        missing: list[str] = []

        if len(v) < 12:
            missing.append("at least 12 characters")
        if not re.search(r"[A-Z]", v):
            missing.append("an uppercase letter")
        if not re.search(r"[a-z]", v):
            missing.append("a lowercase letter")
        if not re.search(r"\d", v):
            missing.append("a digit")
        if not re.search(rf"[{special_chars}]", v):
            missing.append("a special character (e.g. !@#$%^&*()_+-=[]{};:'\"\\|,.<>/?)")

        if missing:
            raise ValueError("Password must contain " + ", ".join(missing))
        return v


class TOTPSetupResponse(BaseModel):
    """Returned when a user enables TOTP MFA."""

    otpauth_url: str = Field(..., description="OTPAuth URL to encode in QR code")
    secret: str = Field(..., description="Base32 TOTP secret (show once, then store)")

    model_config = {"json_schema_extra": {"example": {
        "otpauth_url": "otpauth://totp/ClinNote%20AI:dr.smith@hospital.org?secret=BASE32SECRET&issuer=ClinNote%20AI",
        "secret": "BASE32SECRET",
    }}}


class LogoutResponse(BaseModel):
    """Response body for logout endpoint."""

    message: str = Field(default="Successfully logged out")
