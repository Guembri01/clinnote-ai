from __future__ import annotations
"""
ClinNote AI — Patient Schemas
================================
"""


import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PatientCreate(BaseModel):
    """
    Data required to create a new patient record.
    PHI fields (first_name, last_name, dob) are encrypted by the service layer
    before persistence.
    """

    mrn: str = Field(..., description="Medical Record Number (will be encrypted)")
    first_name: str | None = Field(None, description="Patient first name (will be encrypted)")
    last_name: str | None = Field(None, description="Patient last name (will be encrypted)")
    dob: str | None = Field(None, description="Date of birth ISO-8601 (will be encrypted)")
    encounter_id: str | None = None
    org_id: str | None = None

    model_config = {"json_schema_extra": {"example": {
        "mrn": "MRN-001234",
        "first_name": "Jane",
        "last_name": "Doe",
        "dob": "1985-03-22",
        "encounter_id": "ENC-5678",
    }}}


class PatientRead(BaseModel):
    """Decrypted patient data returned to authorised callers."""

    id: uuid.UUID
    mrn: str
    first_name: str | None
    last_name: str | None
    dob: str | None
    encounter_id: str | None
    org_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
