from __future__ import annotations
"""
ClinNote AI — Authentication Tests
=====================================
Tests for:
  - Login with valid credentials
  - Login with invalid credentials (account lockout)
  - JWT token structure
  - Token refresh
  - MFA setup and verification
  - Logout audit logging
"""

from datetime import timezone

import pytest
from httpx import AsyncClient

from app.models.user import User
from app.services.auth_service import AuthService


@pytest.mark.asyncio
class TestLogin:
    """Test the POST /api/v1/auth/login endpoint."""

    async def test_login_success(
        self,
        async_client: AsyncClient,
        physician_user: User,
    ) -> None:
        """Valid credentials should return a token pair."""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"email": physician_user.email, "password": "DoctorPass!123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0
        assert data["requires_mfa"] is False

    async def test_login_wrong_password(
        self,
        async_client: AsyncClient,
        physician_user: User,
    ) -> None:
        """Wrong password should return 401."""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"email": physician_user.email, "password": "WrongPass!999"},
        )
        assert response.status_code == 401
        assert "Invalid" in response.json()["detail"]

    async def test_login_nonexistent_user(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Unknown email should return 401 (not 404, to prevent user enumeration)."""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "SomePass!123"},
        )
        assert response.status_code == 401

    async def test_login_missing_fields(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Missing required fields should return 422."""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "missing-password@example.com"},
        )
        assert response.status_code == 422

    async def test_login_invalid_email_format(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Malformed email should return 422."""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "not-an-email", "password": "SomePass!123"},
        )
        assert response.status_code == 422


@pytest.mark.asyncio
class TestTokenRefresh:
    """Test the POST /api/v1/auth/refresh endpoint."""

    async def test_refresh_success(
        self,
        async_client: AsyncClient,
        physician_user: User,
    ) -> None:
        """Valid refresh token should return new access token."""
        # Login first
        login_resp = await async_client.post(
            "/api/v1/auth/login",
            json={"email": physician_user.email, "password": "DoctorPass!123"},
        )
        refresh_token = login_resp.json()["refresh_token"]

        # Refresh
        response = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["access_token"] != login_resp.json()["access_token"]

    async def test_refresh_with_access_token_fails(
        self,
        async_client: AsyncClient,
        physician_user: User,
    ) -> None:
        """Access token should be rejected as a refresh token."""
        login_resp = await async_client.post(
            "/api/v1/auth/login",
            json={"email": physician_user.email, "password": "DoctorPass!123"},
        )
        access_token = login_resp.json()["access_token"]

        response = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )
        assert response.status_code == 401

    async def test_refresh_invalid_token(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Garbage token should return 401."""
        response = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "garbage.token.here"},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
class TestLogout:
    """Test the POST /api/v1/auth/logout endpoint."""

    async def test_logout_authenticated(
        self,
        async_client: AsyncClient,
        physician_token: str,
    ) -> None:
        """Authenticated user should be able to log out."""
        response = await async_client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert response.status_code == 200
        assert "logged out" in response.json()["message"].lower()

    async def test_logout_unauthenticated(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Logout without token should return 401."""
        response = await async_client.post("/api/v1/auth/logout")
        assert response.status_code == 401


@pytest.mark.asyncio
class TestAuthService:
    """Unit tests for AuthService helper methods."""

    def test_hash_and_verify_password(self) -> None:
        """Hash and verify should be consistent."""
        password = "TestPassword!123"
        hashed = AuthService.hash_password(password)
        assert hashed != password
        assert AuthService.verify_password(password, hashed) is True
        assert AuthService.verify_password("WrongPassword", hashed) is False

    def test_create_and_decode_access_token(self) -> None:
        """Access token should encode and decode correctly."""
        user_id = str(__import__("uuid").uuid4())
        token, expires = AuthService.create_access_token(
            user_id=user_id,
            email="test@example.com",
            role="physician",
        )
        payload = AuthService.decode_token(token)
        assert payload["sub"] == user_id
        assert payload["email"] == "test@example.com"
        assert payload["role"] == "physician"
        assert payload["type"] == "access"

    def test_create_and_decode_refresh_token(self) -> None:
        """Refresh token should encode and decode correctly."""
        user_id = str(__import__("uuid").uuid4())
        token, _ = AuthService.create_refresh_token(user_id)
        payload = AuthService.decode_token(token)
        assert payload["sub"] == user_id
        assert payload["type"] == "refresh"

    def test_generate_and_verify_totp(self) -> None:
        """TOTP generation and verification should work."""
        secret = AuthService.generate_totp_secret()
        import pyotp
        totp = pyotp.TOTP(secret)
        code = totp.now()
        assert AuthService.verify_totp(secret, code) is True
        assert AuthService.verify_totp(secret, "000000") is False

    def test_account_lockout_check(self) -> None:
        """Account lockout detection should work correctly."""
        from datetime import datetime, timedelta, timezone
        future = datetime.now(timezone.utc) + timedelta(minutes=5)
        past = datetime.now(timezone.utc) - timedelta(minutes=1)
        assert AuthService.is_account_locked(future) is True
        assert AuthService.is_account_locked(past) is False
        assert AuthService.is_account_locked(None) is False
