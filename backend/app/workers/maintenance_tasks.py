"""ClinNote AI — periodic maintenance tasks (run by Celery Beat)."""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, delete

from app.workers.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models.soap_note import SOAPNote, NoteStatus

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.maintenance_tasks.purge_expired_notes")
def purge_expired_notes():
    """Mark DRAFT notes EXPIRED and hard-delete those expired > 7 days ago."""
    return asyncio.run(_purge_expired_notes())


async def _purge_expired_notes():
    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)
        # Step 1: mark draft notes whose expires_at < now as EXPIRED
        result = await db.execute(
            select(SOAPNote).where(
                SOAPNote.status == NoteStatus.DRAFT,
                SOAPNote.expires_at != None,  # noqa: E711
                SOAPNote.expires_at < now,
            )
        )
        rows = result.scalars().all()
        for n in rows:
            n.status = NoteStatus.EXPIRED
        # Step 2: hard-delete notes that were marked EXPIRED > 7 days ago
        cutoff = now - timedelta(days=7)
        await db.execute(
            delete(SOAPNote).where(
                SOAPNote.status == NoteStatus.EXPIRED,
                SOAPNote.updated_at < cutoff,
            )
        )
        await db.commit()
        logger.info("purge_expired_notes: marked=%d", len(rows))
        return {"marked_expired": len(rows)}


@celery_app.task(name="app.workers.maintenance_tasks.purge_stale_audio")
def purge_stale_audio():
    """Clear in-memory audio buffers older than RECORDING_MAX_DURATION."""
    from app.api.v1.websocket import _audio_buffers  # type: ignore
    # Note: this is in-memory only. In production move to Redis with TTL.
    # For now, log the count and return.
    n = len(_audio_buffers)
    logger.info("purge_stale_audio: in-memory buffer count=%d", n)
    return {"in_memory_buffers": n}


@celery_app.task(name="app.workers.maintenance_tasks.archive_old_audit_logs")
def archive_old_audit_logs():
    """Stub for archiving audit logs older than 7 years (HIPAA retention).
    Real impl would move rows to cold storage / partition swap."""
    logger.info("archive_old_audit_logs: stub — implement against cold storage")
    return {"archived": 0}
