from __future__ import annotations
"""
ClinNote AI — Shared API Dependencies
========================================
FastAPI dependency injection utilities for authentication, RBAC,
and database session management.
"""


import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole
from app.services.auth_service import AuthService, ACCESS_TOKEN_TYPE

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency: decode JWT and return the authenticated User.

    Args:
        token: Bearer token from Authorization header.
        db   : Async database session.

    Returns:
        The authenticated User ORM object.

    Raises:
        HTTPException 401: If token is missing, invalid, or user not found/inactive.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    try:
        payload = AuthService.decode_token(token)
    except JWTError:
        raise credentials_exception

    # Ensure this is an access token (not refresh or mfa_pending)
    token_type = payload.get("type")
    if token_type != ACCESS_TOKEN_TYPE:
        raise credentials_exception

    user_id_str: str | None = payload.get("sub")
    if not user_id_str:
        raise credentials_exception

    try:
        # Validate format, but store as string for SQLite String(36) column
        uuid.UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id_str))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact your administrator.",
        )

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Dependency alias: ensure user is active."""
    return current_user


def require_roles(*roles: UserRole):
    """
    Dependency factory that enforces role-based access control.

    Args:
        *roles: Allowed UserRole values.

    Returns:
        FastAPI dependency function that raises 403 if the user's role is not allowed.

    Example:
        @router.get("/admin/users", dependencies=[Depends(require_roles(UserRole.ADMIN))])
    """
    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in roles]}",
            )
        return current_user
    return _check


def get_client_ip(request: Request) -> str:
    """Extract client IP from request (respects X-Forwarded-For)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# Commonly used dependency combinations
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminOnly = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
PhysicianOrAdmin = Annotated[User, Depends(require_roles(UserRole.PHYSICIAN, UserRole.ADMIN))]
ClinicalStaff = Annotated[
    User,
    Depends(require_roles(UserRole.PHYSICIAN, UserRole.ADMIN, UserRole.NURSE, UserRole.PA))
]
DB = Annotated[AsyncSession, Depends(get_db)]
