from __future__ import annotations
"""
ClinNote AI — FHIR Push API
==============================
Endpoints:
  POST /fhir/push/{note_id}   — Push approved SOAP note to EHR via FHIR
  GET  /fhir/status/{note_id} — Get current FHIR push status for a note
"""


import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.v1.deps import ClinicalStaff, CurrentUser, DB, get_client_ip
from app.models.audit_log import AuditAction
from app.models.soap_note import NoteStatus, SOAPNote
from app.models.ehr_integration import EHRIntegration
from app.schemas.fhir import FHIRPushRequest, FHIRPushResponse, FHIRStatusResponse
from app.services.audit_service import AuditService
from app.services.fhir_service import FHIRService
from app.utils.encryption import get_phi_encryption

router = APIRouter(prefix="/fhir", tags=["FHIR"])


@router.post(
    "/push/{note_id}",
    response_model=FHIRPushResponse,
    summary="Push approved SOAP note to EHR via FHIR R4",
    description=(
        "Create a DocumentReference and DiagnosticReport in the configured EHR "
        "using HL7 FHIR R4. Note must be in APPROVED status. "
        "Retries up to 5 times with exponential backoff."
    ),
)
async def push_to_fhir(
    note_id: uuid.UUID,
    body: FHIRPushRequest,
    request: Request,
    current_user: ClinicalStaff,
    db: DB,
) -> FHIRPushResponse:
    """
    Push an approved SOAP note to the EHR system via FHIR R4.

    Args:
        note_id: UUID of the approved SOAPNote to push.
        body   : FHIRPushRequest with patient FHIR ID and org_id.

    Returns:
        FHIRPushResponse with status and created resource ID.

    Raises:
        404: If note or EHR integration config not found.
        409: If note is not in APPROVED status.
        503: If FHIR push fails after max retries.
    """
    from app.models.user import UserRole

    # Fetch note with codes
    note_result = await db.execute(
        select(SOAPNote)
        .options(selectinload(SOAPNote.icd_codes))
        .where(SOAPNote.id == str(note_id))
    )
    note = note_result.scalar_one_or_none()

    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SOAP note not found")

    if current_user.role != UserRole.ADMIN and str(note.user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if note.status != NoteStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Note must be APPROVED before FHIR push. Current status: {note.status.value}",
        )

    # Look up EHR integration config
    integration_result = await db.execute(
        select(EHRIntegration).where(
            EHRIntegration.org_id == body.org_id,
            EHRIntegration.is_active == True,
        )
    )
    fhir_config = integration_result.scalar_one_or_none()

    if not fhir_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active EHR integration found for organisation '{body.org_id}'",
        )

    # Update status to pending
    note.fhir_push_status = "pending"
    await db.commit()

    enc = get_phi_encryption()
    patient_mrn = enc.decrypt(note.patient_mrn) if note.patient_mrn else None

    try:
        svc = FHIRService()
        result = await svc.push_note_to_ehr(
            note=note,
            fhir_config=fhir_config,
            fhir_patient_id=body.fhir_patient_id,
            fhir_encounter_id=body.fhir_encounter_id,
        )

        note.fhir_push_status = "success"
        note.fhir_resource_id = result.get("fhir_resource_id")
        await db.commit()

        await AuditService.log(
            db=db,
            action=AuditAction.FHIR_PUSH,
            user_id=str(current_user.id),
            resource_type="SOAPNote",
            resource_id=str(note_id),
            patient_mrn=patient_mrn,
            ip_address=get_client_ip(request),
            details=f"FHIR push success: {result.get('fhir_resource_id')}",
        )

        return FHIRPushResponse(
            note_id=note_id,
            status="success",
            fhir_resource_id=result.get("fhir_resource_id"),
            message=result.get("message", "Successfully pushed to EHR"),
            timestamp=datetime.now(timezone.utc),
        )

    except Exception as exc:
        note.fhir_push_status = "failed"
        await db.commit()

        await AuditService.log(
            db=db,
            action=AuditAction.FHIR_PUSH_FAILED,
            user_id=str(current_user.id),
            resource_type="SOAPNote",
            resource_id=str(note_id),
            patient_mrn=patient_mrn,
            ip_address=get_client_ip(request),
            details=f"FHIR push failed: {str(exc)[:200]}",
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"FHIR push failed after retries: {str(exc)[:200]}",
        )


@router.get(
    "/status/{note_id}",
    response_model=FHIRStatusResponse,
    summary="Get FHIR push status for a note",
)
async def get_fhir_status(
    note_id: uuid.UUID,
    current_user: ClinicalStaff,
    db: DB,
) -> FHIRStatusResponse:
    """
    Check the current FHIR push status for a SOAP note.

    Returns: pending | success | failed | None (never pushed)
    """
    from app.models.user import UserRole

    result = await db.execute(select(SOAPNote).where(SOAPNote.id == str(note_id)))
    note = result.scalar_one_or_none()

    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SOAP note not found")

    if current_user.role != UserRole.ADMIN and str(note.user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return FHIRStatusResponse(
        note_id=note_id,
        fhir_push_status=note.fhir_push_status,
        fhir_resource_id=note.fhir_resource_id,
        last_updated=note.updated_at,
    )
