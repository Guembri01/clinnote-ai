from __future__ import annotations
"""
ClinNote AI — Celery Transcription Tasks
==========================================
Background task to run final Whisper transcription after recording ends.

Flow:
  1. Recording session status changes to COMPLETED
  2. This task is enqueued: process_final_transcript(session_id)
  3. Task fetches audio bytes from temp storage / Redis cache
  4. Sends to DeepInfra Whisper v3 for final high-accuracy transcription
  5. Saves Transcript record to DB (encrypted)
  6. Enqueues generate_soap_note task
  7. Notifies connected WebSocket clients

HIPAA Note:
  Audio bytes are stored in Redis only during processing.
  After transcription, the audio key is deleted from Redis immediately.
  The Transcript text is encrypted before database insertion.
"""


import asyncio
import logging
import uuid
from datetime import datetime, timezone

import redis as redis_sync

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="app.workers.transcription_tasks.process_final_transcript",
)
def process_final_transcript(self, session_id: str) -> dict:
    """
    Celery task: Run final Whisper transcription for a completed recording session.

    Args:
        session_id: UUID string of the RecordingSession to process.

    Returns:
        dict with keys: session_id, transcript_id, word_count, status

    Raises:
        Retries up to 3 times on transient failures (Whisper API errors).
    """
    logger.info("Starting final transcription for session %s", session_id)

    try:
        result = asyncio.get_event_loop().run_until_complete(
            _process_final_transcript_async(session_id)
        )
        # Drop the in-memory audio buffer (PHI) now that the transcript is durable.
        try:
            from app.api.v1.websocket import clear_audio_buffer
            clear_audio_buffer(session_id)
        except Exception as cleanup_exc:  # pragma: no cover — best-effort cleanup
            logger.warning("Audio buffer cleanup failed for %s: %s", session_id, cleanup_exc)
        return result
    except Exception as exc:
        logger.error("Transcription task failed for session %s: %s", session_id, exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            # Mark session as FAILED in DB
            asyncio.get_event_loop().run_until_complete(
                _mark_session_failed(session_id, str(exc))
            )
            # Terminal failure — also drop the in-memory audio buffer.
            try:
                from app.api.v1.websocket import clear_audio_buffer
                clear_audio_buffer(session_id)
            except Exception as cleanup_exc:  # pragma: no cover
                logger.warning(
                    "Audio buffer cleanup failed for %s after terminal error: %s",
                    session_id, cleanup_exc,
                )
            raise


async def _process_final_transcript_async(session_id: str) -> dict:
    """
    Async implementation of the transcription task.

    Args:
        session_id: UUID string of the recording session.

    Returns:
        Task result dict.
    """
    from app.database import AsyncSessionLocal
    from app.models.recording_session import RecordingSession, SessionStatus
    from app.models.transcript import Transcript
    from app.services.transcription_service import TranscriptionService
    from app.utils.encryption import get_phi_encryption
    from app.config import get_settings
    import redis.asyncio as aioredis
    from sqlalchemy import select

    settings = get_settings()
    enc = get_phi_encryption()

    async with AsyncSessionLocal() as db:
        # Fetch session
        result = await db.execute(
            select(RecordingSession).where(
                RecordingSession.id == uuid.UUID(session_id)
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Fetch audio from Redis
        redis_client = aioredis.from_url(settings.REDIS_URL)
        audio_key = f"audio:{session_id}"
        audio_bytes = await redis_client.get(audio_key)

        if not audio_bytes:
            logger.warning("No audio found in Redis for session %s — using empty", session_id)
            audio_bytes = b""

        # Transcribe
        async with TranscriptionService() as svc:
            transcript_data = await svc.transcribe_final(
                audio_bytes=audio_bytes,
                session_id=session_id,
            )

        # Delete audio from Redis immediately (zero-retention)
        await redis_client.delete(audio_key)
        await redis_client.aclose()

        # Encrypt transcript text before storage
        encrypted_raw = enc.encrypt(transcript_data["raw_text"])
        encrypted_corrected = enc.encrypt(transcript_data["text"])

        # Check for existing transcript (idempotency)
        existing = await db.execute(
            select(Transcript).where(Transcript.session_id == uuid.UUID(session_id))
        )
        transcript = existing.scalar_one_or_none()

        if transcript:
            transcript.raw_text = encrypted_raw
            transcript.corrected_text = encrypted_corrected
            transcript.diarization = transcript_data["diarization"]
            transcript.word_count = transcript_data["word_count"]
            transcript.language = transcript_data["language"]
            transcript.confidence = transcript_data["confidence"]
        else:
            transcript = Transcript(
                session_id=uuid.UUID(session_id),
                raw_text=encrypted_raw,
                corrected_text=encrypted_corrected,
                diarization=transcript_data["diarization"],
                word_count=transcript_data["word_count"],
                language=transcript_data["language"],
                confidence=transcript_data["confidence"],
            )
            db.add(transcript)

        # Mark audio as deleted
        session.audio_deleted_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(transcript)

        transcript_id = str(transcript.id)
        word_count = transcript.word_count or 0

    # Notify WebSocket clients
    try:
        from app.websocket.manager import ws_manager
        await ws_manager.send_transcript_ready(
            session_id=session_id,
            transcript_id=transcript_id,
            word_count=word_count,
        )
    except Exception as exc:
        logger.warning("WebSocket notification failed: %s", exc)

    # Queue SOAP note generation
    from app.workers.note_tasks import generate_soap_note
    generate_soap_note.apply_async(args=[session_id], countdown=2)

    logger.info(
        "Transcription complete: session=%s transcript=%s words=%d",
        session_id,
        transcript_id,
        word_count,
    )

    return {
        "session_id": session_id,
        "transcript_id": transcript_id,
        "word_count": word_count,
        "status": "completed",
    }


async def _mark_session_failed(session_id: str, error: str) -> None:
    """Mark a recording session as FAILED in the database."""
    from app.database import AsyncSessionLocal
    from app.models.recording_session import RecordingSession, SessionStatus
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(RecordingSession).where(
                RecordingSession.id == uuid.UUID(session_id)
            )
        )
        session = result.scalar_one_or_none()
        if session:
            session.status = SessionStatus.FAILED
            session.session_metadata = {
                **(session.session_metadata or {}),
                "failure_reason": error,
                "failed_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.commit()
