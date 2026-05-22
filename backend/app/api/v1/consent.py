from __future__ import annotations
"""
ClinNote AI — Consent API
===========================
Endpoints:
  POST /consent/record — Record patient consent before recording begins

HIPAA Note:
  Patient consent is a legal and regulatory requirement before any ambient
  recording of a clinical encounter. Consent timestamp and IP are stored
  as part of the RecordingSession and are immutable after recording.
"""


import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.api.v1.deps import ClinicalStaff, CurrentUser, DB, get_client_ip
from app.models.audit_log import AuditAction
from app.models.recording_session import RecordingSession, SessionStatus
from app.schemas.recording import ConsentRequest
from app.services.audit_service import AuditService

router = APIRouter(prefix="/consent", tags=["Recordings"])


@router.post(
    "/record",
    summary="Record patient consent",
    description=(
        "Record that verbal or written patient consent has been obtained before "
        "starting ambient audio capture. Transitions the session from "
        "PENDING_CONSENT to RECORDING status."
    ),
    status_code=status.HTTP_200_OK,
)
async def record_consent(
    body: ConsentRequest,
    request: Request,
    current_user: ClinicalStaff,
    db: DB,
) -> dict:
    """
    Mark a recording session as having received patient consent.

    Transitions the session status from PENDING_CONSENT → RECORDING.
    Records consent timestamp and IP address for audit trail.

    Args:
        body: ConsentRequest with session_id and optional consent notes.

    Returns:
        Confirmation dict with session_id, status, and consent timestamp.

    Raises:
        404: If the session does not exist.
        403: If the session belongs to a different clinician.
        409: If the session is not in PENDING_CONSENT status.
    """
    from app.models.user import UserRole

    result = await db.execute(
        select(RecordingSession).where(RecordingSession.id == str(body.session_id))
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording session not found",
        )

    # Ownership check
    if current_user.role != UserRole.ADMIN and str(session.user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied — this session belongs to another clinician",
        )

    if session.status != SessionStatus.PENDING_CONSENT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Session is in '{session.status.value}' status. Consent can only be recorded for PENDING_CONSENT sessions.",
        )

    now = datetime.now(timezone.utc)
    ip = get_client_ip(request)

    # Record consent
    session.consent_recorded_at = now
    session.consent_ip = ip
    session.status = SessionStatus.RECORDING
    session.start_time = now

    # Merge consent notes into session metadata
    if body.notes:
        session.session_metadata = {
            **(session.session_metadata or {}),
            "consent_notes": body.notes,
            "consent_type": body.consent_type,
        }

    await AuditService.log(
        db=db,
        action=AuditAction.CONSENT_RECORDED,
        user_id=str(current_user.id),
        resource_type="RecordingSession",
        resource_id=str(session.id),
        ip_address=ip,
        details=f"Consent type: {body.consent_type}",
    )
    await AuditService.log(
        db=db,
        action=AuditAction.START_RECORDING,
        user_id=str(current_user.id),
        resource_type="RecordingSession",
        resource_id=str(session.id),
        ip_address=ip,
    )
    await db.commit()

    return {
        "session_id": str(body.session_id),
        "status": "recording",
        "consent_recorded_at": now.isoformat(),
        "message": f"Consent recorded ({body.consent_type}). Recording has started.",
    }
