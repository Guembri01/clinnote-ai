from __future__ import annotations
"""
ClinNote AI — Audit Middleware
================================
HIPAA-required request logging middleware that captures:
  - All API requests with method, path, user, and IP
  - PHI-accessing route patterns (automatically inferred from path)

This middleware does NOT replace explicit AuditService.log() calls in routes —
it provides a background safety net for uncaught PHI access patterns.

HIPAA Note:
  Response bodies are NEVER logged to prevent accidental PHI exposure in logs.
  Request bodies for POST /auth routes are redacted.
"""


import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("clinnote.audit")

# URL path patterns that involve PHI access
PHI_PATH_PREFIXES = (
    "/api/v1/patients",
    "/api/v1/recordings",
    "/api/v1/transcripts",
    "/api/v1/notes",
    "/api/v1/documents",
    "/api/v1/fhir",
)

# Sensitive paths where request body must never be logged
REDACT_BODY_PATHS = (
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/verify-mfa",
    "/api/v1/auth/refresh",
)


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Starlette/FastAPI middleware that logs all HTTP requests for HIPAA audit.

    Logged fields:
      - Timestamp, method, path, status code, duration
      - User-Agent, remote IP
      - Whether the path involves PHI access
      - User ID (from JWT claim if available)

    Never logged:
      - Request / response bodies
      - Authorization header values
      - Cookie values
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()

        # Extract minimal metadata (no PHI, no credentials)
        remote_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")[:256]
        method = request.method
        path = request.url.path
        is_phi_route = path.startswith(PHI_PATH_PREFIXES)

        # Process the request
        response: Response = await call_next(request)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Extract user from request state (set by JWT dependency if authenticated)
        user_id = getattr(request.state, "user_id", None) or "anonymous"

        log_level = logging.WARNING if response.status_code >= 400 else logging.INFO

        # Tag anonymous auth failures with a structured reason so SIEM tooling
        # can distinguish missing-token vs expired vs invalid-signature events.
        # The actual reason is set by the auth dependency on request.state.auth_failure_reason.
        # TODO(security): persist LOGIN_FAILED_ANONYMOUS rows to AuditLog from the
        #   auth dependency (not here) — middleware lacks a DB session and writing
        #   one synchronously would block the response. Enum value is already added
        #   to app.models.audit_log.AuditAction so the writer can use it.
        auth_failure_reason = getattr(request.state, "auth_failure_reason", None)
        action_tag = ""
        if response.status_code == 401 and user_id == "anonymous":
            action_tag = " | action=LOGIN_FAILED_ANONYMOUS"
            if auth_failure_reason:
                action_tag += f" | reason={auth_failure_reason}"

        logger.log(
            log_level,
            "REQUEST | %s %s | status=%d | user=%s | ip=%s | duration=%sms | phi=%s%s",
            method,
            path,
            response.status_code,
            user_id,
            remote_ip,
            duration_ms,
            "yes" if is_phi_route else "no",
            action_tag,
        )

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """
        Extract the real client IP, respecting X-Forwarded-For if behind a proxy.

        Args:
            request: FastAPI Request object.

        Returns:
            IP address string.
        """
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP in the chain (original client)
            return forwarded_for.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"
