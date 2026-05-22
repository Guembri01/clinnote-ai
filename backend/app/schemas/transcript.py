from __future__ import annotations
"""
ClinNote AI — Transcript Schemas
===================================
"""


import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DiarizationSegment(BaseModel):
    speaker: str
    start: float
    end: float
    text: str


class TranscriptRead(BaseModel):
    """Decrypted transcript data returned to authorised callers."""

    id: uuid.UUID
    session_id: uuid.UUID
    raw_text: str | None
    corrected_text: str | None
    diarization: list[DiarizationSegment] | None
    word_count: int | None
    language: str | None
    confidence: float | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TranscriptEdit(BaseModel):
    """Physician correction payload for the transcript."""

    corrected_text: str = Field(..., min_length=1, description="Physician-corrected transcript text")

    model_config = {"json_schema_extra": {"example": {
        "corrected_text": "Patient presents with acute upper respiratory infection..."
    }}}
