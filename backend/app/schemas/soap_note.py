from __future__ import annotations
"""
ClinNote AI — SOAP Note Schemas
==================================
"""


import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ICDCodeItem(BaseModel):
    code: str
    description: str
    confidence: float | None = None
    is_primary: bool = False


class CPTCodeItem(BaseModel):
    code: str
    description: str
    confidence: float | None = None


class SOAPSectionDetail(BaseModel):
    """A single SOAP section with AI-generated and physician-edited text."""
    type: str
    ai_generated_text: str
    physician_edited_text: str | None = None
    is_modified: bool = False
    last_modified_at: str | None = None
    last_modified_by: str | None = None


class SOAPNoteRead(BaseModel):
    """Decrypted SOAP note returned to authorised callers."""

    id: uuid.UUID
    session_id: uuid.UUID
    user_id: uuid.UUID
    patient_name: str | None = None
    patient_mrn: str | None
    encounter_id: str | None = None
    status: str
    # Flat fields (kept for backward compatibility)
    subjective: str | None
    objective: str | None
    assessment: str | None
    plan: str | None
    # Structured sections expected by the frontend SOAPNoteEditor
    sections: dict[str, Any] = {}
    specialty: str | None
    icd_codes: list[ICDCodeItem] = []
    cpt_codes: list[CPTCodeItem] = []
    approved_at: datetime | None
    fhir_push_status: str | None
    fhir_resource_id: str | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SOAPNoteEdit(BaseModel):
    """Physician edits to a draft SOAP note."""

    subjective: str | None = Field(None, description="S — Subjective section text")
    objective: str | None = Field(None, description="O — Objective section text")
    assessment: str | None = Field(None, description="A — Assessment section text")
    plan: str | None = Field(None, description="P — Plan section text")
    icd_codes: list[ICDCodeItem] | None = Field(None, description="Replace ICD-10 code list")
    cpt_codes: list[CPTCodeItem] | None = Field(None, description="Replace CPT code list")

    model_config = {"json_schema_extra": {"example": {
        "subjective": "Patient is a 45-year-old male presenting with 3 days of sore throat...",
        "objective": "Temp 38.2°C, BP 122/78, HR 88...",
        "assessment": "1. Acute pharyngitis (J02.9)\n2. Rule out streptococcal infection",
        "plan": "1. Rapid strep test\n2. Acetaminophen 500mg q6h PRN\n3. Return if fever persists",
    }}}


class ApproveRequest(BaseModel):
    """Request body to approve a SOAP note."""

    signature_pin: str | None = Field(None, description="Optional physician PIN for e-signature")
    attestation: str = Field(
        default="I attest that this note accurately reflects the clinical encounter.",
        description="Attestation statement"
    )


class SOAPGenerateRequest(BaseModel):
    """Trigger manual SOAP note regeneration from existing transcript."""

    specialty: str = Field(default="primary_care", description="Clinical specialty for prompt template")
    additional_context: str | None = Field(None, description="Extra context for AI generation")
