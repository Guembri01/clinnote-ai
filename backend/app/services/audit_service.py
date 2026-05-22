from __future__ import annotations
"""
ClinNote AI — HIPAA Audit Service
====================================
Creates append-only audit log entries for all PHI access and system actions.

HIPAA 45 CFR § 164.312(b):
  "Implement hardware, software, and/or procedural mechanisms that record
   and examine activity in information systems that contain or use ePHI."

Rules:
  - AuditLog rows are NEVER updated or deleted.
  - patient_mrn in audit log is AES-256 encrypted.
  - All PHI access (VIEW_PHI, VIEW_NOTE, VIEW_PATIENT, etc.) must be logged.
  - Failed login attempts are logged for security monitoring.
"""


import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditAction, AuditLog
from app.utils.encryption import get_phi_encryption

logger = logging.getLogger(__name__)


class AuditService:
    """
    Append-only HIPAA audit logging service.

    Usage:
        await AuditService.log(
            db=db,
            user_id=current_user.id,
            action=AuditAction.VIEW_PHI,
            resource_type="SOAPNote",
            resource_id=str(note.id),
            patient_mrn="MRN-001234",
            ip_address=request.client.host,
        )
    """

    @staticmethod
    async def log(
        db: AsyncSession,
        action: AuditAction,
        user_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        patient_mrn: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: str | None = None,
    ) -> AuditLog:
        """
        Create an immutable audit log entry.

        Args:
            db           : Async database session.
            action       : AuditAction enum value.
            user_id      : UUID of the acting user (None for system actions).
            resource_type: Type of the accessed resource (e.g. "SOAPNote").
            resource_id  : ID of the accessed resource.
            patient_mrn  : Patient MRN (will be encrypted before storage).
            ip_address   : Remote IP address of the request.
            user_agent   : Browser/client user-agent string.
            details      : Optional free-text details. MUST NOT contain PHI.

        Returns:
            The created AuditLog ORM object.

        Note:
            This method only inserts — never updates or deletes audit records.
        """
        enc = get_phi_encryption()
        encrypted_mrn = enc.encrypt(patient_mrn) if patient_mrn else None

        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            patient_mrn=encrypted_mrn,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
        )
        db.add(entry)
        # Flush to generate ID; the session commit happens in the request lifecycle
        await db.flush()

        logger.info(
            "AUDIT | action=%s user=%s resource=%s/%s ip=%s",
            action.value,
            user_id or "SYSTEM",
            resource_type or "-",
            resource_id or "-",
            ip_address or "-",
        )

        return entry

    @staticmethod
    async def log_login(
        db: AsyncSession,
        user_id: str,
        ip_address: str | None,
        user_agent: str | None,
        success: bool,
    ) -> AuditLog:
        """
        Convenience method to log a login attempt.

        Args:
            db         : Async database session.
            user_id    : UUID of the user attempting login.
            ip_address : Remote IP address.
            user_agent : Client user-agent string.
            success    : True if login succeeded, False if failed.

        Returns:
            Created AuditLog entry.
        """
        action = AuditAction.LOGIN if success else AuditAction.LOGIN_FAILED
        details = "Successful authentication" if success else "Failed authentication attempt"
        return await AuditService.log(
            db=db,
            action=action,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
        )

    @staticmethod
    async def log_phi_access(
        db: AsyncSession,
        user_id: str,
        resource_type: str,
        resource_id: str,
        patient_mrn: str | None,
        ip_address: str | None,
        action: AuditAction = AuditAction.VIEW_PHI,
    ) -> AuditLog:
        """
        Convenience method to log any PHI access event.

        Args:
            db           : Async database session.
            user_id      : UUID of the user accessing PHI.
            resource_type: Type of resource accessed.
            resource_id  : ID of the accessed resource.
            patient_mrn  : Patient MRN (encrypted before storage).
            ip_address   : Remote IP address.
            action       : Specific audit action (default VIEW_PHI).

        Returns:
            Created AuditLog entry.
        """
        return await AuditService.log(
            db=db,
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            patient_mrn=patient_mrn,
            ip_address=ip_address,
        )

    @staticmethod
    async def get_recent_logs(
        db: AsyncSession,
        limit: int = 100,
        user_id: str | None = None,
        action: AuditAction | None = None,
    ) -> list[AuditLog]:
        """
        Retrieve recent audit log entries (admin-only).

        Args:
            db      : Async database session.
            limit   : Maximum entries to return.
            user_id : Filter by specific user (None = all users).
            action  : Filter by action type (None = all actions).

        Returns:
            List of AuditLog ORM objects ordered by timestamp descending.
        """
        from sqlalchemy import select, desc

        stmt = select(AuditLog).order_by(desc(AuditLog.timestamp)).limit(limit)

        if user_id:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if action:
            stmt = stmt.where(AuditLog.action == action)

        result = await db.execute(stmt)
        return list(result.scalars().all())
