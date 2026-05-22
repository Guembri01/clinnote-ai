from __future__ import annotations
"""
ClinNote AI — User Schemas
============================
"""


import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=12)
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    role: str = Field(default="viewer")
    specialty: str | None = None
    npi_number: str | None = None
    org_id: str | None = None
    ehr_system: str | None = None


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    role: str
    specialty: str | None
    npi_number: str | None
    org_id: str | None
    ehr_system: str | None
    is_active: bool
    totp_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    specialty: str | None = None
    npi_number: str | None = None
    org_id: str | None = None
    ehr_system: str | None = None
    is_active: bool | None = None
    role: str | None = None


class UserSummary(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    role: str
    specialty: str | None

    model_config = {"from_attributes": True}
