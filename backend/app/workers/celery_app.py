from __future__ import annotations
"""
ClinNote AI — Celery Application Configuration
================================================
Celery instance for background task processing.
Broker and result backend: Redis.

Tasks:
  - process_final_transcript(session_id): Runs final Whisper transcription
  - generate_soap_note(session_id): Runs GPT-4.1-nano SOAP generation

Run worker with:
  celery -A app.workers.celery_app worker --loglevel=info
"""


from celery import Celery

from app.config import get_settings
from app.workers.beat_schedule import CELERYBEAT_SCHEDULE

settings = get_settings()

celery_app = Celery(
    "clinnote",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.workers.transcription_tasks",
        "app.workers.note_tasks",
        "app.workers.maintenance_tasks",
    ],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Task behavior
    task_acks_late=True,        # Acknowledge after task completes (prevents loss)
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # One task at a time per worker (medical accuracy)
    # Result expiry
    result_expires=3600,        # 1 hour
    # Rate limiting (prevent overwhelming AI APIs)
    task_annotations={
        "app.workers.transcription_tasks.process_final_transcript": {
            "rate_limit": "10/m",
        },
        "app.workers.note_tasks.generate_soap_note": {
            "rate_limit": "20/m",
        },
    },
    # Retry on connection errors
    broker_connection_retry_on_startup=True,
    # Task routing
    task_routes={
        "app.workers.transcription_tasks.*": {"queue": "transcription"},
        "app.workers.note_tasks.*": {"queue": "notes"},
    },
    # Beat schedule (periodic maintenance tasks)
    beat_schedule=CELERYBEAT_SCHEDULE,
)
