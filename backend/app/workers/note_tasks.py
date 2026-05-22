from __future__ import annotations
"""
ClinNote AI — Celery SOAP Note Generation Tasks
=================================================
Background task to generate SOAP notes from finalized transcripts.

Flow:
  1. process_final_transcript enqueues generate_soap_note(session_id)
  2. Task fetches Transcript from DB, decrypts it
  3. Calls GPT-4.1-nano with specialty-specific prompt
  4. Creates SOAPNote + ICDCode + CPTCode records (encrypted)
  5. Sets expires_at = now + NOTE_EXPIRY_HOURS (24h default)
  6. Notifies WebSocket clients that note is ready

HIPAA Note:
  Decrypted transcript text is sent to OpenAI under BAA.
  SOAP note sections are re-encrypted before DB storage.
  The original AI response is stored in original_ai_content for audit.
"""


import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="app.workers.note_tasks.generate_soap_note",
)
def generate_soap_note(self, session_id: str, specialty: str = "primary_care") -> dict:
    """
    Celery task: Generate a SOAP note from the finalized transcript.

    Args:
        session_id: UUID string of the RecordingSession.
        specialty : Clinical specialty key for prompt template selection.

    Returns:
        dict with keys: session_id, note_id, status

    Raises:
        Retries up to 3 times on AI API failures.
    """
    logger.info("Starting SOAP generation for session %s", session_id)

    try:
        result = asyncio.get_event_loop().run_until_complete(
            _generate_soap_async(session_id, specialty)
        )
        return result
    except Exception as exc:
        logger.error("SOAP generation failed for session %s: %s", session_id, exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error("SOAP generation permanently failed for session %s", session_id)
            raise


async def _generate_soap_async(session_id: str, specialty: str) -> dict:
    """
    Async implementation of SOAP note generation.

    Args:
        session_id: UUID string of the recording session.
        specialty : Clinical specialty key.

    Returns:
        Task result dict.
    """
    from app.database import AsyncSessionLocal
    from app.models.recording_session import RecordingSession
    from app.models.transcript import Transcript
    from app.models.soap_note import SOAPNote, NoteStatus
    from app.models.icd_code import ICDCode
    from app.models.cpt_code import CPTCode
    from app.models.user import User
    from app.services.soap_service import SOAPService
    from app.utils.encryption import get_phi_encryption
    from app.config import get_settings
    from sqlalchemy import select

    settings = get_settings()
    enc = get_phi_encryption()

    async with AsyncSessionLocal() as db:
        # Fetch session + transcript
        session_result = await db.execute(
            select(RecordingSession).where(
                RecordingSession.id == uuid.UUID(session_id)
            )
        )
        session = session_result.scalar_one_or_none()
        if not session:
            raise ValueError(f"Session {session_id} not found")

        transcript_result = await db.execute(
            select(Transcript).where(Transcript.session_id == uuid.UUID(session_id))
        )
        transcript = transcript_result.scalar_one_or_none()
        if not transcript:
            raise ValueError(f"Transcript for session {session_id} not found")

        # Fetch user for specialty context
        user_result = await db.execute(
            select(User).where(User.id == session.user_id)
        )
        user = user_result.scalar_one_or_none()

        # Use user's specialty if not overridden
        effective_specialty = specialty
        if user and user.specialty and specialty == "primary_care":
            # Map user specialty to template key
            specialty_map = {
                "cardiology": "cardiology",
                "psychiatry": "psychiatry",
                "psychology": "psychiatry",
                "orthopedics": "orthopedics",
                "orthopaedics": "orthopedics",
                "pediatrics": "pediatrics",
                "paediatrics": "pediatrics",
                "internal medicine": "internal_medicine",
                "emergency medicine": "emergency_medicine",
                "emergency": "emergency_medicine",
                "neurology": "neurology",
                "primary care": "primary_care",
                "family medicine": "primary_care",
            }
            effective_specialty = specialty_map.get(
                user.specialty.lower(), "primary_care"
            )

        # Decrypt transcript for AI processing
        corrected_text = enc.decrypt(transcript.corrected_text) or enc.decrypt(transcript.raw_text) or ""

        if not corrected_text.strip():
            logger.warning("Empty transcript for session %s — using placeholder", session_id)
            corrected_text = "No transcript available."

        # Build patient context (non-PHI)
        patient_context = {
            "encounter_id": session.encounter_id,
            "specialty": effective_specialty,
            "encounter_type": "ambulatory",
        }

        # Generate SOAP note via GPT-4.1-nano
        svc = SOAPService()
        soap_data = await svc.generate_soap_note(
            transcript=corrected_text,
            patient_context=patient_context,
            specialty=effective_specialty,
        )

        # Encrypt SOAP sections before storage
        expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.NOTE_EXPIRY_HOURS)

        # Check for existing note (idempotency)
        existing_result = await db.execute(
            select(SOAPNote).where(SOAPNote.session_id == uuid.UUID(session_id))
        )
        note = existing_result.scalar_one_or_none()

        if note:
            # Update existing note
            note.subjective = enc.encrypt(soap_data.get("subjective", ""))
            note.objective = enc.encrypt(soap_data.get("objective", ""))
            note.assessment = enc.encrypt(soap_data.get("assessment", ""))
            note.plan = enc.encrypt(soap_data.get("plan", ""))
            note.original_ai_content = {
                "subjective": soap_data.get("subjective"),
                "objective": soap_data.get("objective"),
                "assessment": soap_data.get("assessment"),
                "plan": soap_data.get("plan"),
            }
            note.specialty = effective_specialty
            note.status = NoteStatus.DRAFT
            note.expires_at = expires_at
        else:
            note = SOAPNote(
                session_id=uuid.UUID(session_id),
                user_id=session.user_id,
                patient_mrn=session.patient_mrn,
                status=NoteStatus.DRAFT,
                specialty=effective_specialty,
                subjective=enc.encrypt(soap_data.get("subjective", "")),
                objective=enc.encrypt(soap_data.get("objective", "")),
                assessment=enc.encrypt(soap_data.get("assessment", "")),
                plan=enc.encrypt(soap_data.get("plan", "")),
                original_ai_content={
                    "subjective": soap_data.get("subjective"),
                    "objective": soap_data.get("objective"),
                    "assessment": soap_data.get("assessment"),
                    "plan": soap_data.get("plan"),
                },
                expires_at=expires_at,
            )
            db.add(note)
            await db.flush()  # get note.id

        # Delete old codes if regenerating
        if note.id:
            await db.execute(
                __import__("sqlalchemy", fromlist=["delete"]).delete(ICDCode).where(
                    ICDCode.note_id == note.id
                )
            )
            await db.execute(
                __import__("sqlalchemy", fromlist=["delete"]).delete(CPTCode).where(
                    CPTCode.note_id == note.id
                )
            )

        # Create ICD codes
        for icd_item in soap_data.get("icd10_codes", []):
            if icd_item.get("code"):
                db.add(ICDCode(
                    note_id=note.id,
                    code=icd_item["code"],
                    description=icd_item.get("description", ""),
                    confidence=icd_item.get("confidence"),
                    is_primary=icd_item.get("is_primary", False),
                ))

        # Create CPT codes
        for cpt_item in soap_data.get("cpt_codes", []):
            if cpt_item.get("code"):
                db.add(CPTCode(
                    note_id=note.id,
                    code=cpt_item["code"],
                    description=cpt_item.get("description", ""),
                    confidence=cpt_item.get("confidence"),
                ))

        await db.commit()
        await db.refresh(note)
        note_id = str(note.id)

    # Notify WebSocket clients
    try:
        from app.websocket.manager import ws_manager
        await ws_manager.send_soap_ready(
            session_id=session_id,
            note_id=note_id,
        )
    except Exception as exc:
        logger.warning("WebSocket soap_ready notification failed: %s", exc)

    logger.info(
        "SOAP generation complete: session=%s note=%s specialty=%s",
        session_id,
        note_id,
        effective_specialty,
    )

    return {
        "session_id": session_id,
        "note_id": note_id,
        "specialty": effective_specialty,
        "status": "completed",
    }
