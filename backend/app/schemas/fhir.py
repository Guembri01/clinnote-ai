from __future__ import annotations
"""
ClinNote AI — FHIR Schemas
============================
Request/response schemas for HL7 FHIR R4 push operations.
"""


import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class FHIRPushRequest(BaseModel):
    """
    Request body to push an approved SOAP note to the EHR via FHIR.

    Args:
        fhir_patient_id : FHIR Patient resource ID in the target EHR.
        fhir_encounter_id: Optional FHIR Encounter resource ID.
        org_id          : Organisation ID to look up EHR integration config.
    """

    fhir_patient_id: str = Field(..., description="FHIR Patient resource ID in target EHR")
    fhir_encounter_id: str | None = Field(None, description="FHIR Encounter resource ID")
    org_id: str = Field(..., description="Organisation ID for EHR integration lookup")

    model_config = {"json_schema_extra": {"example": {
        "fhir_patient_id": "Patient/12345",
        "fhir_encounter_id": "Encounter/67890",
        "org_id": "org-001",
    }}}


class FHIRPushResponse(BaseModel):
    """
    Result of a FHIR push operation.

    Attributes:
        note_id       : UUID of the pushed SOAP note.
        status        : success | failed | pending.
        fhir_resource_id: FHIR DocumentReference ID created in the EHR.
        message       : Human-readable status message.
        timestamp     : When the push was attempted.
    """

    note_id: uuid.UUID
    status: str
    fhir_resource_id: str | None = None
    message: str
    timestamp: datetime

    model_config = {"from_attributes": True}


class FHIRStatusResponse(BaseModel):
    """Current FHIR push status for a note."""

    note_id: uuid.UUID
    fhir_push_status: str | None
    fhir_resource_id: str | None
    last_updated: datetime
