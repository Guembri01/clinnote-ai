from __future__ import annotations
"""
ClinNote AI — FastAPI Application Entry Point
================================================
Ambient Clinical Voice-to-EHR Note Generator

HIPAA-compliant backend featuring:
  - AES-256 encryption for all PHI at rest
  - Append-only audit logging
  - JWT access (15 min) + refresh (7 day) tokens
  - TOTP MFA with account lockout
  - Session inactivity enforcement (15 min)
  - Zero-retention audio policy
  - WebSocket real-time transcription streaming
  - HL7 FHIR R4 EHR integration

Tech stack:
  FastAPI + SQLAlchemy 2.0 async + PostgreSQL + Redis + Celery
  DeepInfra Whisper v3 + OpenAI GPT-4.1-nano + Azure Document Intelligence
"""


import asyncio
import logging
import logging.config
import sys
import time
import uuid
from contextlib import asynccontextmanager

# Windows: psycopg3 requires SelectorEventLoop (not ProactorEventLoop)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from typing import AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import api_router
from app.api.v1.websocket import router as ws_router
from app.config import get_settings
from app.database import create_tables
from app.middleware.audit_middleware import AuditMiddleware
from app.middleware.session_timeout import SessionTimeoutMiddleware
from app.rate_limit import limiter

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("clinnote")

settings = get_settings()
logger.setLevel(settings.LOG_LEVEL.upper())


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan handler.

    Startup:
      - Create database tables (idempotent via CREATE TABLE IF NOT EXISTS)
      - Validate encryption key is set
      - Log startup banner

    Shutdown:
      - Log shutdown message
    """
    logger.info("=" * 60)
    logger.info("ClinNote AI API — Starting up")
    logger.info("Environment: %s", settings.ENVIRONMENT)
    logger.info("Database URL: %s", settings.DATABASE_URL.split("@")[-1])

    # Validate encryption key
    _is_prod = settings.ENVIRONMENT.lower() in ("production", "prod")
    if not settings.ENCRYPTION_KEY:
        if _is_prod:
            raise RuntimeError(
                "ENCRYPTION_KEY is not set in production. Refusing to start: "
                "PHI encryption requires a stable 44-char URL-safe base64 Fernet key."
            )
        logger.warning(
            "ENCRYPTION_KEY is not set — PHI encryption will use a random key "
            "(data will not survive restarts). Set ENCRYPTION_KEY in production!"
        )
    else:
        # Confirm key format for ops visibility (length only — never log the key itself).
        logger.info(
            "ENCRYPTION_KEY configured: length_ok=%s (len=%d, required>=44)",
            len(settings.ENCRYPTION_KEY) >= 44,
            len(settings.ENCRYPTION_KEY),
        )

    # Create tables
    try:
        await create_tables()
        logger.info("Database tables created / verified")
    except Exception as exc:
        logger.error("Database initialization failed: %s", exc)
        raise

    logger.info("ClinNote AI API — Ready to serve requests")
    logger.info("=" * 60)

    yield

    logger.info("ClinNote AI API — Shutting down")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="ClinNote AI API",
    description=(
        "**ClinNote AI** — Ambient Clinical Voice-to-EHR Note Generator\n\n"
        "HIPAA-compliant backend for real-time transcription and AI-powered "
        "SOAP note generation from clinical encounters.\n\n"
        "## Security\n"
        "- All endpoints require Bearer JWT authentication\n"
        "- PHI fields are AES-256 encrypted at rest\n"
        "- All PHI access is audit-logged\n"
        "- Session inactivity timeout: 15 minutes\n\n"
        "## Authentication\n"
        "1. `POST /api/v1/auth/login` with email + password\n"
        "2. If MFA enabled, `POST /api/v1/auth/verify-mfa` with TOTP code\n"
        "3. Include `Authorization: Bearer <access_token>` on all requests\n"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={
        "name": "ClinNote AI Support",
        "email": "support@clinnote.ai",
    },
    license_info={
        "name": "Proprietary",
    },
    openapi_tags=[
        {"name": "Authentication", "description": "Login, MFA, token management"},
        {"name": "Users", "description": "User account management (admin)"},
        {"name": "Patients", "description": "Patient record management (PHI encrypted)"},
        {"name": "Recordings", "description": "Ambient recording session lifecycle"},
        {"name": "Transcription", "description": "Transcript access and editing"},
        {"name": "Notes", "description": "SOAP note generation, editing, and approval"},
        {"name": "Documents", "description": "Lab report and intake form OCR"},
        {"name": "FHIR", "description": "HL7 FHIR R4 EHR integration"},
        {"name": "ICD Codes", "description": "ICD-10-CM code search and lookup"},
        {"name": "Admin", "description": "Administrative reporting and audit logs"},
        {"name": "WebSocket", "description": "Real-time audio streaming"},
    ],
)

# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    expose_headers=["X-Request-ID"],
)

# ---------------------------------------------------------------------------
# Custom middleware (order matters — outermost is processed first)
# ---------------------------------------------------------------------------
# Session timeout must run before route handlers
app.add_middleware(SessionTimeoutMiddleware)
# Audit middleware runs on every request
app.add_middleware(AuditMiddleware)


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response


# ---------------------------------------------------------------------------
# Request-ID logging middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "method=%s path=%s status=%d duration_ms=%.1f request_id=%s",
        request.method, request.url.path, response.status_code, duration_ms, request_id,
    )
    return response

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(api_router, prefix="/api/v1")
app.include_router(ws_router)  # WebSocket routes at root level


# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all exception handler.
    Returns a generic 500 response without leaking internal details.
    """
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.exception(
        "Unhandled exception request_id=%s: %s %s — %s: %s",
        request_id,
        request.method,
        request.url.path,
        type(exc).__name__,
        str(exc)[:200],
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred. Please try again or contact support.",
            "code": "INTERNAL_SERVER_ERROR",
            "request_id": request_id,
        },
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc) -> JSONResponse:
    detail = exc.detail if hasattr(exc, "detail") else "Resource not found"
    return JSONResponse(status_code=404, content={"detail": detail})


@app.exception_handler(405)
async def method_not_allowed_handler(request: Request, exc) -> JSONResponse:
    detail = exc.detail if hasattr(exc, "detail") else "Method not allowed"
    return JSONResponse(status_code=405, content={"detail": detail})


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get(
    "/health",
    tags=["Health"],
    summary="API health check",
    description="Returns 200 if the API is running. Checks database connectivity.",
)
async def health_check() -> dict:
    """
    Health check endpoint for load balancers and monitoring.

    Checks:
      - API is running
      - Database is reachable
      - Encryption key is configured

    Returns:
        JSON with status, version, and component health.
    """
    from app.database import AsyncSessionLocal
    from sqlalchemy import text

    db_status = "ok"
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"error: {type(exc).__name__}"

    return {
        "status": "healthy" if db_status == "ok" else "degraded",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "components": {
            "database": db_status,
            "encryption": "configured" if settings.ENCRYPTION_KEY else "warning: not set",
        },
    }
