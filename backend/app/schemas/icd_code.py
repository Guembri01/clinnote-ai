from __future__ import annotations
"""
ClinNote AI — ICD Code Schemas
==================================
"""


import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ICDCodeRead(BaseModel):
    id: uuid.UUID
    note_id: uuid.UUID
    code: str
    description: str
    confidence: float | None
    is_primary: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ICDCodeSearch(BaseModel):
    """Result item for ICD-10 code search."""

    code: str = Field(..., description="ICD-10-CM code (e.g. J06.9)")
    description: str = Field(..., description="Full description of the diagnosis")
    category: str | None = Field(None, description="Chapter/category of the code")

    model_config = {"json_schema_extra": {"example": {
        "code": "J06.9",
        "description": "Acute upper respiratory infection, unspecified",
        "category": "J00-J06 Acute upper respiratory infections",
    }}}
