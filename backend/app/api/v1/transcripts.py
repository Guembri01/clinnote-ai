from __future__ import annotations
"""
ClinNote AI — Transcripts API
================================
Endpoints:
  GET   /transcripts/{session_id}  — Get transcript for a session
  PATCH /transcripts/{id}          — Apply physician corrections
"""


import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.api.v1.deps import ClinicalStaff, CurrentUser, DB, get_client_ip
from app.models.audit_log import AuditAction
from app.models.transcript import Transcript
from app.models.recording_session import RecordingSession
from app.schemas.transcript import TranscriptRead, TranscriptEdit
from app.services.audit_service import AuditService
from app.utils.encryption import get_phi_encryption

router = APIRouter(prefix="/transcripts", tags=["Transcription"])


def _decrypt_transcript(transcript: Transcript) -> TranscriptRead:
    """Decrypt encrypted fields and return a TranscriptRead schema."""
    enc = get_phi_encryption()
    return TranscriptRead(
        id=transcript.id,
        session_id=transcript.session_id,
        raw_text=enc.decrypt(transcript.raw_text),
        corrected_text=enc.decrypt(transcript.corrected_text),
        diarization=transcript.diarization,
        word_count=transcript.word_count,
        language=transcript.language,
        confidence=transcript.confidence,
        created_at=transcript.created_at,
        updated_at=transcript.updated_at,
    )


@router.get(
    "/{session_id}",
    response_model=TranscriptRead,
    summary="Get transcript for a recording session",
    description=(
        "Retrieve the full (decrypted) transcript for a session. "
        "Returns 404 if transcription has not completed yet. "
        "All access is audit-logged as PHI access."
    ),
)
async def get_transcript(
    session_id: uuid.UUID,
    request: Request,
    current_user: ClinicalStaff,
    db: DB,
) -> TranscriptRead:
    """
    Get the transcript for a recording session.

    Returns decrypted raw and corrected text with diarization segments.
    Only the owning clinician (or admin) can access.
    """
    from app.models.user import UserRole

    # Validate session ownership
    session_result = await db.execute(
        select(RecordingSession).where(RecordingSession.id == str(session_id))
    )
    session = session_result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recording session not found")

    if current_user.role != UserRole.ADMIN and str(session.user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Fetch transcript
    transcript_result = await db.execute(
        select(Transcript).where(Transcript.session_id == str(session_id))
    )
    transcript = transcript_result.scalar_one_or_none()

    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not yet available. Transcription may still be in progress.",
        )

    # Decrypt MRN for audit log
    enc = get_phi_encryption()
    patient_mrn = enc.decrypt(session.patient_mrn) if session.patient_mrn else None

    await AuditService.log_phi_access(
        db=db,
        user_id=str(current_user.id),
        resource_type="Transcript",
        resource_id=str(transcript.id),
        patient_mrn=patient_mrn,
        ip_address=get_client_ip(request),
        action=AuditAction.VIEW_TRANSCRIPT,
    )

    return _decrypt_transcript(transcript)


@router.patch(
    "/{transcript_id}",
    response_model=TranscriptRead,
    summary="Apply physician corrections to transcript",
    description=(
        "Update the corrected_text of a transcript with physician edits. "
        "The original raw_text from Whisper is preserved unchanged."
    ),
)
async def edit_transcript(
    transcript_id: uuid.UUID,
    body: TranscriptEdit,
    request: Request,
    current_user: ClinicalStaff,
    db: DB,
) -> TranscriptRead:
    """
    Save physician corrections to the transcript.

    Args:
        transcript_id: UUID of the Transcript to update.
        body         : TranscriptEdit with corrected_text.

    Returns:
        Updated TranscriptRead with decrypted content.
    """
    from app.models.user import UserRole

    transcript_result = await db.execute(
        select(Transcript).where(Transcript.id == str(transcript_id))
    )
    transcript = transcript_result.scalar_one_or_none()

    if not transcript:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transcript not found")

    # Validate ownership via session
    session_result = await db.execute(
        select(RecordingSession).where(RecordingSession.id == str(transcript.session_id))
    )
    session = session_result.scalar_one_or_none()

    if session and current_user.role != UserRole.ADMIN and str(session.user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    enc = get_phi_encryption()

    # Encrypt and save corrected text
    transcript.corrected_text = enc.encrypt(body.corrected_text)
    transcript.word_count = len(body.corrected_text.split())

    await AuditService.log(
        db=db,
        action=AuditAction.EDIT_TRANSCRIPT,
        user_id=str(current_user.id),
        resource_type="Transcript",
        resource_id=str(transcript_id),
        ip_address=get_client_ip(request),
        details=f"Physician corrections applied — {transcript.word_count} words",
    )
    await db.commit()
    await db.refresh(transcript)

    return _decrypt_transcript(transcript)
