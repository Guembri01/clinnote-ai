from __future__ import annotations
"""
ClinNote AI — HIPAA Session Inactivity Timeout Middleware
===========================================================
Enforces a 15-minute inactivity timeout on all authenticated API calls.

HIPAA 45 CFR § 164.312(a)(2)(iii):
  "Implement electronic procedures that terminate an electronic session
   after a predetermined time of inactivity."

Implementation:
  - Access tokens are issued with 15-minute expiry (handled by JWT).
  - This middleware adds an additional check: if the token was issued
    more than SESSION_INACTIVITY_TIMEOUT seconds ago, the request is
    rejected with 401 even if the JWT signature is still valid.
  - The frontend is expected to refresh the access token while the user
    is active (using the refresh token before the access token expires).
  - Inactivity = no successful API call within the window.
"""


import logging
from datetime import datetime, timezone
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings

logger = logging.getLogger("clinnote.session")
settings = get_settings()

# Paths that do not require session timeout enforcement
EXCLUDED_PATHS = (
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/verify-mfa",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
)


class SessionTimeoutMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces HIPAA inactivity session timeout.

    On every authenticated request:
      1. Extracts the JWT from the Authorization header.
      2. Decodes the 'iat' (issued-at) claim.
      3. Rejects the request if now - iat > SESSION_INACTIVITY_TIMEOUT.

    Note: This relies on the JWT 'iat' claim. Since access tokens are
    issued fresh on each login/refresh, the iat reflects the last activity
    time from the client's perspective.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip enforcement for excluded paths
        path = request.url.path
        if any(path.startswith(excluded) for excluded in EXCLUDED_PATHS):
            return await call_next(request)

        # Only enforce on requests with Authorization header
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return await call_next(request)

        token = auth_header.removeprefix("Bearer ").strip()
        if not token:
            return await call_next(request)

        # Decode JWT to get issued-at time
        try:
            from app.services.auth_service import AuthService
            payload = AuthService.decode_token(token)
        except JWTError:
            # JWT validity is enforced by the route dependency — skip here
            return await call_next(request)

        iat: int | None = payload.get("iat")
        if iat is None:
            return await call_next(request)

        now = datetime.now(timezone.utc)
        issued_at = datetime.fromtimestamp(iat, tz=timezone.utc)
        elapsed_seconds = (now - issued_at).total_seconds()

        if elapsed_seconds > settings.SESSION_INACTIVITY_TIMEOUT:
            logger.info(
                "Session timeout enforced: token age=%.0fs limit=%ds user=%s",
                elapsed_seconds,
                settings.SESSION_INACTIVITY_TIMEOUT,
                payload.get("sub", "unknown"),
            )
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Session expired due to inactivity. Please log in again.",
                    "code": "SESSION_TIMEOUT",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Store user_id in request state for audit middleware
        request.state.user_id = payload.get("sub")
        request.state.user_role = payload.get("role")

        return await call_next(request)
