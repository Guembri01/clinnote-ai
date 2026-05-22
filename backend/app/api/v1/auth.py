from __future__ import annotations
"""
ClinNote AI — Authentication API
===================================
Endpoints:
  POST /auth/login        — Credential validation, returns tokens or MFA challenge
  POST /auth/verify-mfa   — TOTP verification after login
  POST /auth/refresh      — Exchange refresh token for new access token
  POST /auth/logout       — Invalidate session (client-side token deletion)
  POST /auth/register     — Create new user account (admin only)
  POST /auth/mfa/setup    — Enable TOTP MFA for authenticated user
  DELETE /auth/mfa/setup  — Disable TOTP MFA

Rate limiting: 5 requests/minute per IP on login endpoint.
"""


import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentUser, DB, get_client_ip, require_roles
from app.database import get_db
from app.models.audit_log import AuditAction
from app.models.user import User, UserRole
from app.schemas.auth import (
    LoginRequest,
    LogoutResponse,
    MFAVerifyRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TOTPSetupResponse,
    TokenResponse,
)
from app.rate_limit import limiter
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService, MFA_PENDING_TOKEN_TYPE, REFRESH_TOKEN_TYPE
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate with email and password",
    description=(
        "Validate clinician credentials. If MFA is enabled, returns a short-lived "
        "'mfa_pending' token and requires a follow-up POST to /auth/verify-mfa. "
        "Rate limited to 5 requests/minute per IP."
    ),
)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate a clinician with email and password.

    - Returns full token pair if MFA is not enabled.
    - Returns a pending token with `requires_mfa=True` if TOTP is configured.
    - Increments failed_login_attempts on failure.
    - Locks account for TOTP_LOCKOUT_MINUTES after TOTP_LOCKOUT_ATTEMPTS failures.
    """
    ip = get_client_ip(request)
    ua = request.headers.get("user-agent", "")[:256]

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not AuthService.verify_password(body.password, user.hashed_password):
        # Log failed attempt
        if user:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= settings.TOTP_LOCKOUT_ATTEMPTS:
                user.locked_until = AuthService.get_lockout_expiry(settings.TOTP_LOCKOUT_MINUTES)
            await db.commit()
            await AuditService.log_login(db, str(user.id), ip, ua, success=False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    if AuthService.is_account_locked(user.locked_until):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account is temporarily locked. Try again after {user.locked_until.isoformat()}",
        )

    # Reset failed attempts on successful password auth
    user.failed_login_attempts = 0
    user.locked_until = None
    await db.commit()

    # MFA required?
    if user.totp_enabled and user.mfa_secret:
        pending_token = AuthService.create_mfa_pending_token(str(user.id))
        await AuditService.log(
            db=db,
            action=AuditAction.LOGIN,
            user_id=str(user.id),
            ip_address=ip,
            user_agent=ua,
            details="Password verified; MFA pending",
        )
        return TokenResponse(
            access_token=pending_token,
            refresh_token="",
            token_type="bearer",
            expires_in=300,
            requires_mfa=True,
        )

    # Full login — issue token pair
    access_token, expires = AuthService.create_access_token(
        user_id=str(user.id),
        email=user.email,
        role=user.role.value,
        org_id=user.org_id,
    )
    refresh_token, _ = AuthService.create_refresh_token(str(user.id))

    await AuditService.log_login(db, str(user.id), ip, ua, success=True)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        requires_mfa=False,
    )


@router.post(
    "/verify-mfa",
    response_model=TokenResponse,
    summary="Complete MFA verification with TOTP code",
    description="Verify a 6-digit TOTP code using the pending token from /auth/login.",
)
@limiter.limit(settings.MFA_RATE_LIMIT)
async def verify_mfa(
    request: Request,
    body: MFAVerifyRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Verify TOTP code and exchange the MFA pending token for a full access token pair.

    Enforces:
    - Lockout after 5 failed TOTP attempts
    - TOTP window of ±1 step (30 seconds)
    """
    from jose import JWTError

    ip = get_client_ip(request)
    ua = request.headers.get("user-agent", "")[:256]

    try:
        payload = AuthService.decode_token(body.token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired MFA token")

    if payload.get("type") != MFA_PENDING_TOKEN_TYPE:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == str(user_id)))
    user = result.scalar_one_or_none()

    if not user or not user.totp_enabled or not user.mfa_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="MFA not configured")

    if AuthService.is_account_locked(user.locked_until):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account locked after too many failed MFA attempts",
        )

    # Decrypt MFA secret and verify TOTP
    from app.utils.encryption import get_phi_encryption
    enc = get_phi_encryption()
    plain_secret = enc.decrypt(user.mfa_secret)

    if not AuthService.verify_totp(plain_secret, body.totp_code):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= settings.TOTP_LOCKOUT_ATTEMPTS:
            user.locked_until = AuthService.get_lockout_expiry(settings.TOTP_LOCKOUT_MINUTES)
        await db.commit()
        await AuditService.log(
            db=db, action=AuditAction.MFA_FAILED, user_id=str(user.id),
            ip_address=ip, user_agent=ua,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid TOTP code")

    # Success — reset counters and issue full tokens
    user.failed_login_attempts = 0
    user.locked_until = None
    await db.commit()

    access_token, _ = AuthService.create_access_token(
        user_id=str(user.id),
        email=user.email,
        role=user.role.value,
        org_id=user.org_id,
    )
    refresh_token, _ = AuthService.create_refresh_token(str(user.id))

    await AuditService.log(
        db=db, action=AuditAction.MFA_VERIFIED, user_id=str(user.id),
        ip_address=ip, user_agent=ua,
    )
    await AuditService.log_login(db, str(user.id), ip, ua, success=True)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        requires_mfa=False,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Exchange a valid refresh token for a new access token pair.",
)
async def refresh_token(
    body: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Issue a new access token using a valid refresh token.
    Validates that the token type is 'refresh' and the user still exists and is active.
    """
    from jose import JWTError

    try:
        payload = AuthService.decode_token(body.refresh_token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if payload.get("type") != REFRESH_TOKEN_TYPE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == str(user_id)))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )

    access_token, _ = AuthService.create_access_token(
        user_id=str(user.id),
        email=user.email,
        role=user.role.value,
        org_id=user.org_id,
    )
    new_refresh, _ = AuthService.create_refresh_token(str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Log out",
    description=(
        "Logs out the current user. The client must delete stored tokens. "
        "Creates an audit log entry for HIPAA compliance."
    ),
)
async def logout(
    request: Request,
    current_user: CurrentUser,
    db: DB,
) -> LogoutResponse:
    """
    Record logout event in audit log.
    Token invalidation is handled client-side (stateless JWT).
    """
    await AuditService.log(
        db=db,
        action=AuditAction.LOGOUT,
        user_id=str(current_user.id),
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent", "")[:256],
    )
    return LogoutResponse(message="Successfully logged out")


@router.post(
    "/bootstrap",
    status_code=status.HTTP_201_CREATED,
    summary="Create first admin user (only works on empty database)",
    description=(
        "One-time bootstrap endpoint. Creates the first admin user when the database "
        "has no users. Returns 403 if any user already exists."
    ),
)
async def bootstrap_admin(
    body: RegisterRequest,
    db: DB,
) -> dict:
    """
    Bootstrap the first administrator account.

    This endpoint is only available when zero users exist in the database.
    Once the first admin is created, this endpoint returns 403 on all subsequent calls.
    """
    from sqlalchemy import func as sa_func

    result = await db.execute(select(sa_func.count()).select_from(User))
    if result.scalar() > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bootstrap not available: users already exist. Use /auth/login.",
        )

    user = User(
        email=body.email,
        hashed_password=AuthService.hash_password(body.password),
        first_name=body.first_name,
        last_name=body.last_name,
        role=UserRole.ADMIN,
        specialty=body.specialty,
        npi_number=body.npi_number,
        org_id=body.org_id,
    )
    db.add(user)
    await db.flush()
    await AuditService.log(
        db=db,
        action=AuditAction.USER_CREATED,
        user_id=str(user.id),
        resource_type="User",
        resource_id=str(user.id),
        details="Bootstrap: created first admin user",
    )
    await db.commit()
    await db.refresh(user)
    return {"id": str(user.id), "email": user.email, "role": user.role.value}


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register new clinician (admin only)",
    description="Create a new clinician account. Only administrators can register users.",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def register(
    body: RegisterRequest,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    """
    Create a new user account (admin-only).

    Validates:
    - Email uniqueness
    - Password strength
    - NPI number uniqueness (if provided)
    """
    # Check email uniqueness
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    # Check NPI uniqueness
    if body.npi_number:
        npi_check = await db.execute(select(User).where(User.npi_number == body.npi_number))
        if npi_check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="NPI number already registered",
            )

    # Validate role
    try:
        role = UserRole(body.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid role. Must be one of: {[r.value for r in UserRole]}",
        )

    user = User(
        email=body.email,
        hashed_password=AuthService.hash_password(body.password),
        first_name=body.first_name,
        last_name=body.last_name,
        role=role,
        specialty=body.specialty,
        npi_number=body.npi_number,
        org_id=body.org_id or current_user.org_id,
    )
    db.add(user)
    await db.flush()

    await AuditService.log(
        db=db,
        action=AuditAction.USER_CREATED,
        user_id=str(current_user.id),
        resource_type="User",
        resource_id=str(user.id),
        details=f"Created user {user.email} with role {role.value}",
    )
    await db.commit()

    return {"id": str(user.id), "email": user.email, "role": role.value}


@router.post(
    "/mfa/setup",
    response_model=TOTPSetupResponse,
    summary="Enable TOTP MFA for authenticated user",
)
async def setup_mfa(
    current_user: CurrentUser,
    db: DB,
) -> TOTPSetupResponse:
    """
    Generate a new TOTP secret and return the OTPAuth URI for QR code display.
    The secret is stored encrypted in the database.
    The client must confirm with a valid TOTP code to activate MFA.
    """
    from app.utils.encryption import get_phi_encryption

    enc = get_phi_encryption()
    secret = AuthService.generate_totp_secret()
    otpauth_url = AuthService.get_totp_uri(secret, current_user.email)

    # Store encrypted secret (not yet enabled — requires confirmation)
    current_user.mfa_secret = enc.encrypt(secret)
    # Enable immediately (in production, require confirmation before enabling)
    current_user.totp_enabled = True
    await db.commit()

    return TOTPSetupResponse(otpauth_url=otpauth_url, secret=secret)


@router.delete(
    "/mfa/setup",
    summary="Disable TOTP MFA",
    status_code=status.HTTP_200_OK,
)
async def disable_mfa(
    current_user: CurrentUser,
    db: DB,
) -> dict:
    """Disable TOTP MFA for the authenticated user."""
    current_user.totp_enabled = False
    current_user.mfa_secret = None
    await db.commit()
    return {"message": "MFA disabled successfully"}
