from __future__ import annotations
"""
ClinNote AI — Users API
=========================
Endpoints:
  GET    /users           — List all users (admin only)
  GET    /users/me        — Get own profile
  GET    /users/{id}      — Get user by ID (admin only)
  PATCH  /users/{id}      — Update user (admin only)
  DELETE /users/{id}      — Deactivate user (admin only)
"""


import uuid
from typing import List

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.v1.deps import AdminOnly, CurrentUser, DB, require_roles
from app.models.audit_log import AuditAction
from app.models.user import User, UserRole
from app.schemas.user import UserRead, UserUpdate
from app.services.audit_service import AuditService
from fastapi import Depends

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get own profile",
)
async def get_me(current_user: CurrentUser) -> UserRead:
    """Return the authenticated user's own profile."""
    return UserRead.model_validate(current_user)


@router.get(
    "",
    response_model=List[UserRead],
    summary="List all users (admin only)",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def list_users(
    db: DB,
    skip: int = 0,
    limit: int = 50,
    org_id: str | None = None,
) -> List[UserRead]:
    """
    List clinician accounts in the system.

    Args:
        skip  : Pagination offset.
        limit : Maximum number of results (max 200).
        org_id: Filter by organisation ID.
    """
    limit = min(limit, 200)
    stmt = select(User).offset(skip).limit(limit).order_by(User.created_at.desc())
    if org_id:
        stmt = stmt.where(User.org_id == org_id)
    result = await db.execute(stmt)
    users = result.scalars().all()
    return [UserRead.model_validate(u) for u in users]


@router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Get user by ID (admin only)",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def get_user(
    user_id: uuid.UUID,
    db: DB,
) -> UserRead:
    """Retrieve a specific user account by UUID."""
    result = await db.execute(select(User).where(User.id == str(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserRead.model_validate(user)


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    summary="Update user (admin or self)",
    description="Admins can update any user. Non-admins can update only their own profile (role changes are admin-only).",
)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    current_user: CurrentUser,
    db: DB,
) -> UserRead:
    """
    Update a user's profile or role.

    Admins can update any user. Non-admins can only update their own profile.
    Role changes are always admin-only. Cannot change password through this endpoint.
    """
    # Enforce access: admin can edit anyone, others can only edit themselves
    if current_user.role != UserRole.ADMIN and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required to update other users",
        )

    result = await db.execute(select(User).where(User.id == str(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    update_data = body.model_dump(exclude_unset=True)

    if "role" in update_data:
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin role required to change user roles",
            )
        try:
            update_data["role"] = UserRole(update_data["role"])
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid role. Must be one of: {[r.value for r in UserRole]}",
            )

    for field, value in update_data.items():
        setattr(user, field, value)

    await AuditService.log(
        db=db,
        action=AuditAction.ADMIN_ACTION,
        user_id=str(current_user.id),
        resource_type="User",
        resource_id=str(user.id),
        details=f"Updated fields: {list(update_data.keys())}",
    )
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Deactivate user (admin only)",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def deactivate_user(
    user_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    """
    Deactivate a user account (soft delete — sets is_active=False).
    Admin cannot deactivate their own account.
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account",
        )

    result = await db.execute(select(User).where(User.id == str(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = False
    await AuditService.log(
        db=db,
        action=AuditAction.USER_DEACTIVATED,
        user_id=str(current_user.id),
        resource_type="User",
        resource_id=str(user.id),
        details=f"Deactivated user {user.email}",
    )
    await db.commit()
    return {"message": "User deactivated successfully"}
