from __future__ import annotations
"""
ClinNote AI — Recording Session Schemas
=========================================
"""


import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RecordingSessionCreate(BaseModel):
    """Payload to initiate a new ambient recording session."""

    patient_mrn: str = Field(..., description="Patient MRN (will be encrypted)")
    encounter_id: str | None = None
    session_metadata: dict[str, Any] | None = None

    model_config = {"json_schema_extra": {"example": {
        "patient_mrn": "MRN-001234",
        "encounter_id": "ENC-5678",
        "session_metadata": {"room": "Exam-3", "device": "tablet"},
    }}}


class RecordingSessionRead(BaseModel):
    """Recording session details returned by the API."""

    id: uuid.UUID
    user_id: uuid.UUID
    patient_mrn: str | None
    encounter_id: str | None
    status: str
    consent_recorded_at: datetime | None
    start_time: datetime | None
    end_time: datetime | None
    duration_seconds: int | None
    audio_deleted_at: datetime | None
    session_metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConsentRequest(BaseModel):
    """Record verbal patient consent before starting audio capture."""

    session_id: uuid.UUID = Field(..., description="Recording session ID")
    consent_type: str = Field(default="verbal", description="verbal | written | electronic")
    notes: str | None = Field(None, description="Optional consent notes (no PHI)")

    model_config = {"json_schema_extra": {"example": {
        "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "consent_type": "verbal",
        "notes": "Patient verbally confirmed consent to ambient recording",
    }}}


class RecordingControlResponse(BaseModel):
    """Response to start/stop/pause/resume commands."""

    session_id: uuid.UUID
    status: str
    message: str
    timestamp: datetime
    note_id: uuid.UUID | None = None  # Populated when recording is stopped
