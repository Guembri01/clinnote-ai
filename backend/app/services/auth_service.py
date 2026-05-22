from __future__ import annotations
"""
ClinNote AI — Authentication Service
=======================================
Handles:
  - JWT access + refresh token creation and verification
  - Bcrypt password hashing (cost factor 12)
  - TOTP MFA setup and verification (pyotp)
  - Account lockout after failed attempts

Security notes:
  - Access tokens expire in 15 minutes (HIPAA inactivity requirement)
  - Refresh tokens expire in 7 days
  - TOTP lockout: 5 failed attempts → 5-minute lockout
  - Passwords hashed with bcrypt cost factor 12
"""


import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pyotp
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

# ---------------------------------------------------------------------------
# Password hashing context (bcrypt cost=12)
# ---------------------------------------------------------------------------
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)

# ---------------------------------------------------------------------------
# JWT token types
# ---------------------------------------------------------------------------
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"
MFA_PENDING_TOKEN_TYPE = "mfa_pending"


class AuthService:
    """
    Stateless authentication utility service.
    All methods are pure functions / classmethods — no DB access.
    """

    # ------------------------------------------------------------------ #
    # Password
    # ------------------------------------------------------------------ #

    @staticmethod
    def hash_password(plain_password: str) -> str:
        """
        Hash a plain-text password with bcrypt (cost=12).

        Args:
            plain_password: The user's raw password.

        Returns:
            Bcrypt hash string suitable for database storage.
        """
        return pwd_context.hash(plain_password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a plain password against a stored bcrypt hash.

        Args:
            plain_password: Password provided during login.
            hashed_password: Stored bcrypt hash from the database.

        Returns:
            True if the password matches, False otherwise.
        """
        return pwd_context.verify(plain_password, hashed_password)

    # ------------------------------------------------------------------ #
    # JWT tokens
    # ------------------------------------------------------------------ #

    @staticmethod
    def create_access_token(
        user_id: str,
        email: str,
        role: str,
        org_id: str | None = None,
        extra_claims: dict[str, Any] | None = None,
    ) -> tuple[str, datetime]:
        """
        Create a short-lived JWT access token.

        Args:
            user_id   : UUID of the authenticated user.
            email     : User email (non-PHI claim).
            role      : User role string.
            org_id    : Organisation ID (optional claim).
            extra_claims: Additional JWT claims to include.

        Returns:
            Tuple of (token_string, expiry_datetime).
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        payload: dict[str, Any] = {
            "sub": str(user_id),
            "email": email,
            "role": role,
            "type": ACCESS_TOKEN_TYPE,
            "iat": now,
            "exp": expires,
            "jti": str(uuid.uuid4()),
        }
        if org_id:
            payload["org_id"] = org_id
        if extra_claims:
            payload.update(extra_claims)

        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return token, expires

    @staticmethod
    def create_refresh_token(user_id: str) -> tuple[str, datetime]:
        """
        Create a long-lived JWT refresh token.

        Args:
            user_id: UUID of the authenticated user.

        Returns:
            Tuple of (token_string, expiry_datetime).
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        payload: dict[str, Any] = {
            "sub": str(user_id),
            "type": REFRESH_TOKEN_TYPE,
            "iat": now,
            "exp": expires,
            "jti": str(uuid.uuid4()),
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return token, expires

    @staticmethod
    def create_mfa_pending_token(user_id: str) -> str:
        """
        Create a short-lived token indicating MFA step is pending.
        Used between password verification and TOTP verification.

        Args:
            user_id: UUID of the user who passed password check.

        Returns:
            Signed JWT valid for 5 minutes.
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=5)
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "type": MFA_PENDING_TOKEN_TYPE,
            "iat": now,
            "exp": expires,
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> dict[str, Any]:
        """
        Decode and validate a JWT token.

        Args:
            token: Raw JWT string.

        Returns:
            Decoded payload dictionary.

        Raises:
            JWTError: If the token is invalid, expired, or tampered.
        """
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
            return payload
        except JWTError as exc:
            raise JWTError(f"Invalid token: {exc}") from exc

    @staticmethod
    def get_user_id_from_token(token: str) -> str:
        """
        Extract the user ID (sub claim) from a valid JWT.

        Args:
            token: Valid JWT string.

        Returns:
            User UUID string.

        Raises:
            JWTError: If token is invalid or sub claim missing.
        """
        payload = AuthService.decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise JWTError("Token missing 'sub' claim")
        return user_id

    # ------------------------------------------------------------------ #
    # TOTP MFA
    # ------------------------------------------------------------------ #

    @staticmethod
    def generate_totp_secret() -> str:
        """
        Generate a new random TOTP secret for a user.

        Returns:
            Base32-encoded secret string (store encrypted in DB).
        """
        return pyotp.random_base32()

    @staticmethod
    def get_totp_uri(secret: str, email: str, issuer: str = "ClinNote AI") -> str:
        """
        Generate an OTPAuth URI for QR code generation.

        Args:
            secret: Base32 TOTP secret.
            email : User email (used as account name in authenticator app).
            issuer: App name shown in authenticator app.

        Returns:
            otpauth:// URI string.
        """
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=email, issuer_name=issuer)

    @staticmethod
    def verify_totp(secret: str, code: str, valid_window: int = 1) -> bool:
        """
        Verify a 6-digit TOTP code against the stored secret.

        Args:
            secret      : Base32 TOTP secret (decrypted from DB).
            code        : 6-digit code from the authenticator app.
            valid_window: Number of 30-second windows to allow (1 = ±30 sec).

        Returns:
            True if the code is valid within the window, False otherwise.
        """
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=valid_window)

    # ------------------------------------------------------------------ #
    # Account lockout helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def is_account_locked(locked_until: datetime | None) -> bool:
        """
        Check whether an account is currently locked.

        Args:
            locked_until: The datetime until which the account is locked (UTC).

        Returns:
            True if the account is locked and lock has not expired.
        """
        if locked_until is None:
            return False
        return datetime.now(timezone.utc) < locked_until.replace(tzinfo=timezone.utc) if locked_until.tzinfo is None else datetime.now(timezone.utc) < locked_until

    @staticmethod
    def get_lockout_expiry(lockout_minutes: int = 5) -> datetime:
        """
        Calculate when a new account lockout should expire.

        Args:
            lockout_minutes: Duration of the lockout in minutes.

        Returns:
            UTC datetime when the lockout expires.
        """
        return datetime.now(timezone.utc) + timedelta(minutes=lockout_minutes)
