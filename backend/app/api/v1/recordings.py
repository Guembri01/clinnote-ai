from __future__ import annotations
"""
ClinNote AI — Recording Sessions API
=======================================
Endpoints:
  POST /recordings/start           — Initiate a new recording session
  POST /recordings/{id}/stop       — Stop recording and trigger transcription
  POST /recordings/{id}/pause      — Pause active recording
  POST /recordings/{id}/resume     — Resume paused recording
  GET  /recordings                 — List recording sessions
  GET  /recordings/{id}            — Get session details

Business rules:
  - Consent must be recorded before recording can start (POST /consent/record)
  - Recording auto-stops at RECORDING_MAX_DURATION (120 min, FR-09)
  - Audio bytes are stored in Redis during recording; deleted after transcription
"""


import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.api.v1.deps import ClinicalStaff, CurrentUser, DB, get_client_ip
from app.config import get_settings
from app.models.audit_log import AuditAction
from app.models.patient import Patient
from app.models.recording_session import RecordingSession, SessionStatus
from app.schemas.recording import RecordingControlResponse, RecordingSessionCreate, RecordingSessionRead
from app.services.audit_service import AuditService
from app.utils.encryption import compute_hmac, get_phi_encryption

router = APIRouter(prefix="/recordings", tags=["Recordings"])
settings = get_settings()


def _mask_mrn(encrypted_mrn: str | None) -> str | None:
    """Return partially masked MRN for non-admin display."""
    if not encrypted_mrn:
        return None
    enc = get_phi_encryption()
    try:
        plain = enc.decrypt(encrypted_mrn) or ""
        return f"***{plain[-4:]}" if len(plain) >= 4 else "***"
    except Exception:
        return "***"


@router.post(
    "/start",
    response_model=RecordingSessionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new recording session",
    description=(
        "Create a recording session in PENDING_CONSENT status. "
        "Call POST /consent/record before the session can transition to RECORDING."
    ),
)
async def start_recording(
    body: RecordingSessionCreate,
    request: Request,
    current_user: ClinicalStaff,
    db: DB,
) -> RecordingSessionRead:
    """
    Initiate a new ambient recording session.

    Args:
        body: RecordingSessionCreate with patient MRN and optional metadata.

    Returns:
        RecordingSessionRead with the new session in PENDING_CONSENT status.
    """
    enc = get_phi_encryption()
    # Look up the patient's stored encrypted MRN via HMAC to satisfy the FK constraint.
    # Fernet uses random IVs so re-encrypting the same MRN produces a different ciphertext
    # that would not match the value stored in patients.mrn.
    mrn_hmac = compute_hmac(body.patient_mrn, settings.ENCRYPTION_KEY or "")
    patient_row = await db.execute(select(Patient).where(Patient.mrn_hmac == mrn_hmac))
    patient = patient_row.scalar_one_or_none()
    encrypted_mrn = patient.mrn if patient else enc.encrypt(body.patient_mrn)

    session = RecordingSession(
        user_id=current_user.id,
        patient_mrn=encrypted_mrn,
        encounter_id=body.encounter_id,
        status=SessionStatus.PENDING_CONSENT,
        session_metadata=body.session_metadata or {},
    )
    db.add(session)
    await db.flush()

    await AuditService.log(
        db=db,
        action=AuditAction.CREATE_SESSION,
        user_id=str(current_user.id),
        resource_type="RecordingSession",
        resource_id=str(session.id),
        patient_mrn=body.patient_mrn,
        ip_address=get_client_ip(request),
        details=f"Encounter: {body.encounter_id or 'N/A'}",
    )
    await db.commit()
    await db.refresh(session)

    return RecordingSessionRead.model_validate({
        **{c.name: getattr(session, c.name) for c in session.__table__.columns},
        "patient_mrn": _mask_mrn(session.patient_mrn),
    })


@router.post(
    "/{session_id}/stop",
    response_model=RecordingControlResponse,
    summary="Stop recording and trigger transcription",
    description=(
        "Stop an active or paused recording. Triggers async transcription "
        "via Celery. Audio is deleted from Redis after transcription completes."
    ),
)
async def stop_recording(
    session_id: uuid.UUID,
    request: Request,
    current_user: ClinicalStaff,
    db: DB,
) -> RecordingControlResponse:
    """
    Stop a recording session and enqueue the transcription + SOAP generation pipeline.

    The session transitions to COMPLETED status. The Celery task
    process_final_transcript is enqueued automatically.
    """
    session = await _get_session_or_404(db, session_id, current_user)

    if session.status not in (SessionStatus.RECORDING, SessionStatus.PAUSED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot stop session in status '{session.status.value}'. Must be RECORDING or PAUSED.",
        )

    now = datetime.now(timezone.utc)
    session.status = SessionStatus.COMPLETED
    session.end_time = now

    if session.start_time:
        start = session.start_time.replace(tzinfo=timezone.utc) if session.start_time.tzinfo is None else session.start_time
        session.duration_seconds = int((now - start).total_seconds())

    enc = get_phi_encryption()
    _plain_mrn = enc.decrypt(session.patient_mrn) if session.patient_mrn else None

    await AuditService.log(
        db=db,
        action=AuditAction.STOP_RECORDING,
        user_id=str(current_user.id),
        resource_type="RecordingSession",
        resource_id=str(session_id),
        patient_mrn=_plain_mrn,
        ip_address=get_client_ip(request),
        details=f"Duration: {session.duration_seconds or 0}s",
    )

    # Create a stub SOAPNote immediately so clients can poll it
    from datetime import timedelta
    from app.models.soap_note import NoteStatus, SOAPNote
    stub_note = SOAPNote(
        session_id=session.id,
        user_id=current_user.id,
        patient_mrn=session.patient_mrn,
        status=NoteStatus.DRAFT,
        specialty=(session.session_metadata or {}).get("specialty"),
        subjective=enc.encrypt("Pending AI generation…"),
        objective=enc.encrypt("Pending AI generation…"),
        assessment=enc.encrypt("Pending AI generation…"),
        plan=enc.encrypt("Pending AI generation…"),
        expires_at=now + timedelta(hours=settings.NOTE_EXPIRY_HOURS),
    )
    db.add(stub_note)
    await db.commit()
    await db.refresh(stub_note)

    # Enqueue Celery transcription task
    try:
        from app.workers.transcription_tasks import process_final_transcript
        process_final_transcript.apply_async(args=[str(session_id)])
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Failed to enqueue transcription task: %s", exc)

    return RecordingControlResponse(
        session_id=session_id,
        status="completed",
        message="Recording stopped. Transcription pipeline initiated.",
        timestamp=now,
        note_id=stub_note.id,
    )


@router.post(
    "/{session_id}/pause",
    response_model=RecordingControlResponse,
    summary="Pause active recording",
)
async def pause_recording(
    session_id: uuid.UUID,
    request: Request,
    current_user: ClinicalStaff,
    db: DB,
) -> RecordingControlResponse:
    """Pause a currently active recording session."""
    session = await _get_session_or_404(db, session_id, current_user)

    if session.status != SessionStatus.RECORDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot pause session in status '{session.status.value}'. Must be RECORDING.",
        )

    session.status = SessionStatus.PAUSED
    _enc = get_phi_encryption()
    _plain_mrn_pause = _enc.decrypt(session.patient_mrn) if session.patient_mrn else None
    await AuditService.log(
        db=db,
        action=AuditAction.STOP_RECORDING,
        user_id=str(current_user.id),
        resource_type="RecordingSession",
        resource_id=str(session_id),
        patient_mrn=_plain_mrn_pause,
        ip_address=get_client_ip(request),
        details="Recording paused",
    )
    await db.commit()

    return RecordingControlResponse(
        session_id=session_id,
        status="paused",
        message="Recording paused.",
        timestamp=datetime.now(timezone.utc),
    )


@router.post(
    "/{session_id}/resume",
    response_model=RecordingControlResponse,
    summary="Resume paused recording",
)
async def resume_recording(
    session_id: uuid.UUID,
    request: Request,
    current_user: ClinicalStaff,
    db: DB,
) -> RecordingControlResponse:
    """Resume a paused recording session. Validates max duration hasn't been reached."""
    session = await _get_session_or_404(db, session_id, current_user)

    if session.status != SessionStatus.PAUSED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot resume session in status '{session.status.value}'. Must be PAUSED.",
        )

    # FR-09: Check max duration
    if session.start_time:
        start = session.start_time.replace(tzinfo=timezone.utc) if session.start_time.tzinfo is None else session.start_time
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        if elapsed >= settings.RECORDING_MAX_DURATION:
            session.status = SessionStatus.COMPLETED
            session.end_time = datetime.now(timezone.utc)
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Recording cannot resume: maximum duration of {settings.RECORDING_MAX_DURATION // 60} minutes reached.",
            )

    session.status = SessionStatus.RECORDING
    _enc = get_phi_encryption()
    _plain_mrn_resume = _enc.decrypt(session.patient_mrn) if session.patient_mrn else None
    await AuditService.log(
        db=db,
        action=AuditAction.START_RECORDING,
        user_id=str(current_user.id),
        resource_type="RecordingSession",
        resource_id=str(session_id),
        patient_mrn=_plain_mrn_resume,
        ip_address=get_client_ip(request),
        details="Recording resumed",
    )
    await db.commit()

    return RecordingControlResponse(
        session_id=session_id,
        status="recording",
        message="Recording resumed.",
        timestamp=datetime.now(timezone.utc),
    )


@router.get(
    "",
    response_model=List[RecordingSessionRead],
    summary="List recording sessions",
)
async def list_sessions(
    current_user: CurrentUser,
    db: DB,
    skip: int = 0,
    limit: int = 20,
    status_filter: str | None = None,
) -> List[RecordingSessionRead]:
    """List recording sessions for the current user (clinician sees own, admin sees all)."""
    from app.models.user import UserRole

    limit = min(limit, 100)
    stmt = select(RecordingSession).order_by(RecordingSession.created_at.desc()).offset(skip).limit(limit)

    if current_user.role != UserRole.ADMIN:
        stmt = stmt.where(RecordingSession.user_id == current_user.id)

    if status_filter:
        try:
            stmt = stmt.where(RecordingSession.status == SessionStatus(status_filter))
        except ValueError:
            pass

    result = await db.execute(stmt)
    sessions = result.scalars().all()

    return [
        RecordingSessionRead.model_validate({
            **{c.name: getattr(s, c.name) for c in s.__table__.columns},
            "patient_mrn": _mask_mrn(s.patient_mrn),
        })
        for s in sessions
    ]


@router.get(
    "/{session_id}",
    response_model=RecordingSessionRead,
    summary="Get recording session details",
)
async def get_session(
    session_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
) -> RecordingSessionRead:
    """Get details for a specific recording session."""
    session = await _get_session_or_404(db, session_id, current_user)
    return RecordingSessionRead.model_validate({
        **{c.name: getattr(session, c.name) for c in session.__table__.columns},
        "patient_mrn": _mask_mrn(session.patient_mrn),
    })


async def _get_session_or_404(
    db: DB,
    session_id: uuid.UUID,
    current_user: CurrentUser,
) -> RecordingSession:
    """Fetch session by ID; enforce ownership for non-admin users."""
    from app.models.user import UserRole

    result = await db.execute(
        select(RecordingSession).where(RecordingSession.id == str(session_id))
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recording session not found")

    if current_user.role != UserRole.ADMIN and str(session.user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return session
