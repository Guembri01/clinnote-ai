from __future__ import annotations
"""
ClinNote AI — Patients API
============================
Endpoints:
  POST /patients          — Create patient record
  GET  /patients          — List patients (paginated)
  GET  /patients/{id}     — Get patient by UUID
  GET  /patients/mrn/{mrn}— Get patient by MRN

HIPAA Note:
  All PHI fields (name, DOB) are decrypted only on read and re-encrypted on write.
  MRN is also encrypted in the database.
  Every read access is logged to the audit trail.
"""


import uuid
from typing import List

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.api.v1.deps import ClinicalStaff, CurrentUser, DB, get_client_ip
from app.models.audit_log import AuditAction
from app.models.patient import Patient
from app.schemas.patient import PatientCreate, PatientRead
from app.services.audit_service import AuditService
from app.utils.encryption import compute_hmac, get_phi_encryption
from app.config import get_settings

router = APIRouter(prefix="/patients", tags=["Patients"])


def _decrypt_patient(patient: Patient) -> PatientRead:
    """Decrypt PHI fields and return a PatientRead schema."""
    enc = get_phi_encryption()
    return PatientRead(
        id=patient.id,
        mrn=enc.decrypt(patient.mrn) or patient.mrn,
        first_name=enc.decrypt(patient.enc_first_name),
        last_name=enc.decrypt(patient.enc_last_name),
        dob=enc.decrypt(patient.enc_dob),
        encounter_id=patient.encounter_id,
        org_id=patient.org_id,
        created_at=patient.created_at,
    )


@router.post(
    "",
    response_model=PatientRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create patient record",
    description="Register a new patient. All PHI is encrypted before storage.",
)
async def create_patient(
    body: PatientCreate,
    request: Request,
    current_user: CurrentUser,
    db: DB,
) -> PatientRead:
    """
    Create a new patient record with encrypted PHI fields.

    Args:
        body: PatientCreate payload with MRN and optional name/DOB.

    Returns:
        PatientRead with decrypted PHI (shown once after creation).
    """
    enc = get_phi_encryption()
    settings = get_settings()

    # Check MRN uniqueness using deterministic HMAC (Fernet is non-deterministic)
    mrn_hmac = compute_hmac(body.mrn, settings.ENCRYPTION_KEY or "")
    existing = await db.execute(select(Patient).where(Patient.mrn_hmac == mrn_hmac))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A patient with this MRN already exists",
        )

    encrypted_mrn = enc.encrypt(body.mrn)
    patient = Patient(
        mrn=encrypted_mrn,
        mrn_hmac=mrn_hmac,
        enc_first_name=enc.encrypt(body.first_name) if body.first_name else None,
        enc_last_name=enc.encrypt(body.last_name) if body.last_name else None,
        enc_dob=enc.encrypt(body.dob) if body.dob else None,
        encounter_id=body.encounter_id,
        org_id=body.org_id or current_user.org_id,
    )
    db.add(patient)
    await db.flush()

    await AuditService.log(
        db=db,
        action=AuditAction.CREATE_PATIENT,
        user_id=str(current_user.id),
        resource_type="Patient",
        resource_id=str(patient.id),
        patient_mrn=body.mrn,
        ip_address=get_client_ip(request),
    )
    await db.commit()
    await db.refresh(patient)
    return _decrypt_patient(patient)


@router.get(
    "",
    response_model=List[PatientRead],
    summary="List patients",
    description="Retrieve a paginated list of patients. All PHI access is audit-logged.",
)
async def list_patients(
    request: Request,
    current_user: ClinicalStaff,
    db: DB,
    skip: int = 0,
    limit: int = 20,
) -> List[PatientRead]:
    """List patients with pagination. Requires clinical staff role."""
    limit = min(limit, 100)
    result = await db.execute(
        select(Patient)
        .order_by(Patient.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    patients = result.scalars().all()

    await AuditService.log(
        db=db,
        action=AuditAction.VIEW_PHI,
        user_id=str(current_user.id),
        resource_type="Patient",
        ip_address=get_client_ip(request),
        details=f"Listed {len(patients)} patients",
    )

    return [_decrypt_patient(p) for p in patients]


@router.get(
    "/{patient_id}",
    response_model=PatientRead,
    summary="Get patient by UUID",
)
async def get_patient(
    patient_id: uuid.UUID,
    request: Request,
    current_user: ClinicalStaff,
    db: DB,
) -> PatientRead:
    """Retrieve a patient record by UUID. Audit-logged as PHI access."""
    result = await db.execute(select(Patient).where(Patient.id == str(patient_id)))
    patient = result.scalar_one_or_none()

    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    enc = get_phi_encryption()
    decrypted_mrn = enc.decrypt(patient.mrn) or ""

    await AuditService.log_phi_access(
        db=db,
        user_id=str(current_user.id),
        resource_type="Patient",
        resource_id=str(patient_id),
        patient_mrn=decrypted_mrn,
        ip_address=get_client_ip(request),
        action=AuditAction.VIEW_PATIENT,
    )

    return _decrypt_patient(patient)


@router.get(
    "/mrn/{mrn}",
    response_model=PatientRead,
    summary="Get patient by MRN",
)
async def get_patient_by_mrn(
    mrn: str,
    request: Request,
    current_user: ClinicalStaff,
    db: DB,
) -> PatientRead:
    """Look up a patient by their Medical Record Number using deterministic HMAC index."""
    from app.config import get_settings as _gs
    mrn_hmac = compute_hmac(mrn, _gs().ENCRYPTION_KEY or "")

    result = await db.execute(select(Patient).where(Patient.mrn_hmac == mrn_hmac))
    patient = result.scalar_one_or_none()

    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    await AuditService.log_phi_access(
        db=db,
        user_id=str(current_user.id),
        resource_type="Patient",
        resource_id=str(patient.id),
        patient_mrn=mrn,
        ip_address=get_client_ip(request),
        action=AuditAction.VIEW_PATIENT,
    )

    return _decrypt_patient(patient)
