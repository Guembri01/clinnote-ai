from __future__ import annotations
"""
ClinNote AI — SOAP Notes API
===============================
Endpoints:
  GET  /notes/{id}          — Get SOAP note (decrypted)
  PATCH /notes/{id}         — Edit SOAP note sections
  POST /notes/{id}/approve  — Physician approval / sign
  POST /notes/{id}/generate — Re-generate SOAP note from transcript
"""


import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.v1.deps import ClinicalStaff, CurrentUser, DB, get_client_ip, require_roles
from app.models.audit_log import AuditAction
from app.models.icd_code import ICDCode
from app.models.cpt_code import CPTCode
from app.models.recording_session import RecordingSession
from app.models.soap_note import NoteStatus, SOAPNote
from app.models.transcript import Transcript
from app.models.user import User
from app.schemas.soap_note import (
    ApproveRequest,
    ICDCodeItem,
    CPTCodeItem,
    SOAPGenerateRequest,
    SOAPNoteEdit,
    SOAPNoteRead,
)
from app.services.audit_service import AuditService
from app.utils.encryption import get_phi_encryption, compute_hmac
from app.config import get_settings
from fastapi import Depends
from app.models.user import UserRole
from app.models.patient import Patient

router = APIRouter(prefix="/notes", tags=["Notes"])


@router.get(
    "",
    summary="List SOAP notes for current user",
    description="Returns paginated SOAP notes belonging to the authenticated clinician (admin sees all).",
)
async def list_notes(
    current_user: ClinicalStaff,
    db: DB,
    page: int = 1,
    page_size: int = 20,
    skip: int = 0,
    limit: int = 0,
    status_filter: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> dict:
    """List notes for the current user; returns PaginatedResponse shape."""
    from sqlalchemy import func

    enc = get_phi_encryption()
    resolved_status = status_filter or status

    # Support both page/page_size and legacy skip/limit
    if limit > 0:
        page_size = min(limit, 200)
        page = (skip // page_size) + 1 if page_size else 1

    page = max(1, page)
    page_size = min(max(1, page_size), 200)
    offset = (page - 1) * page_size

    # Base filter
    base_stmt = select(SOAPNote)
    if current_user.role != UserRole.ADMIN:
        base_stmt = base_stmt.where(SOAPNote.user_id == current_user.id)
    if resolved_status:
        try:
            base_stmt = base_stmt.where(SOAPNote.status == NoteStatus(resolved_status))
        except ValueError:
            pass

    # Count total (before search narrowing — we filter post-fetch for encrypted PHI)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Fetch page with user join for physician name
    data_stmt = (
        base_stmt
        .order_by(SOAPNote.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(data_stmt)
    notes = result.scalars().all()

    # Build physician name map
    user_ids = list({str(n.user_id) for n in notes})
    physician_map: dict[str, str] = {}
    if user_ids:
        u_result = await db.execute(
            select(User.id, User.first_name, User.last_name).where(User.id.in_(user_ids))
        )
        for row in u_result:
            physician_map[str(row.id)] = f"{row.first_name} {row.last_name}"

    # Build session map for encounter_id, session_date, and raw encrypted MRN
    session_ids = list({str(n.session_id) for n in notes})
    session_map: dict[str, dict] = {}
    if session_ids:
        s_result = await db.execute(
            select(RecordingSession.id, RecordingSession.encounter_id,
                   RecordingSession.created_at, RecordingSession.patient_mrn)
            .where(RecordingSession.id.in_(session_ids))
        )
        for row in s_result:
            session_map[str(row.id)] = {
                "encounter_id": row.encounter_id or "",
                "session_date": row.created_at.isoformat() if row.created_at else None,
                "patient_mrn_enc": row.patient_mrn,
            }

    # Resolve patient names via Patient table (mrn_hmac lookup)
    settings = get_settings()
    patient_name_map: dict[str, str] = {}
    mrn_enc_set = {v["patient_mrn_enc"] for v in session_map.values() if v.get("patient_mrn_enc")}
    for mrn_enc in mrn_enc_set:
        try:
            plain_mrn = enc.decrypt(mrn_enc)
            if plain_mrn:
                hmac_val = compute_hmac(plain_mrn, settings.ENCRYPTION_KEY or "")
                p_result = await db.execute(
                    select(Patient.mrn, Patient.enc_first_name, Patient.enc_last_name)
                    .where(Patient.mrn_hmac == hmac_val)
                )
                p_row = p_result.first()
                if p_row and (p_row.enc_first_name or p_row.enc_last_name):
                    fn = enc.decrypt(p_row.enc_first_name) if p_row.enc_first_name else ""
                    ln = enc.decrypt(p_row.enc_last_name) if p_row.enc_last_name else ""
                    patient_name_map[mrn_enc] = f"{fn} {ln}".strip() or "Clinical Patient"
                else:
                    patient_name_map[mrn_enc] = "Clinical Patient"
        except Exception:
            patient_name_map[mrn_enc] = "Clinical Patient"

    def _mask_mrn(encrypted: str | None) -> str:
        if not encrypted:
            return "***"
        try:
            plain = enc.decrypt(encrypted) or ""
            return f"***{plain[-4:]}" if len(plain) >= 4 else "***"
        except Exception:
            return "***"

    # Build row dicts with decrypted patient names for search filtering
    rows = []
    for n in notes:
        mrn_enc = session_map.get(str(n.session_id), {}).get("patient_mrn_enc", "")
        patient_name = patient_name_map.get(mrn_enc, "Clinical Patient")
        masked_mrn = _mask_mrn(n.patient_mrn)
        rows.append({
            "id": str(n.id),
            "session_id": str(n.session_id),
            "patient_name": patient_name,
            "patient_mrn": masked_mrn,
            "encounter_id": session_map.get(str(n.session_id), {}).get("encounter_id", ""),
            "status": n.status.value,
            "physician_name": physician_map.get(str(n.user_id), "Physician"),
            "session_date": session_map.get(str(n.session_id), {}).get("session_date") or n.created_at.isoformat(),
            "approved_at": n.approved_at.isoformat() if n.approved_at else None,
            "expires_at": n.expires_at.isoformat() if n.expires_at else None,
            "fhir_pushed_at": None,
            "specialty": n.specialty,
            "fhir_push_status": n.fhir_push_status,
            "created_at": n.created_at.isoformat(),
            "updated_at": n.updated_at.isoformat(),
        })

    # Apply search filter: match only patient name or masked MRN (NOT physician name)
    if search:
        search_lower = search.strip().lower()
        rows = [
            r for r in rows
            if search_lower in r["patient_name"].lower()
            or search_lower in r["patient_mrn"].lower()
        ]

    filtered_total = len(rows) if search else total
    total_pages = max(1, (filtered_total + page_size - 1) // page_size)

    return {
        "data": rows,
        "total": filtered_total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


async def _get_note_with_codes(
    db: DB,
    note_id: uuid.UUID,
    current_user: CurrentUser,
) -> SOAPNote:
    """Fetch note with ICD/CPT codes and validate ownership."""
    result = await db.execute(
        select(SOAPNote)
        .options(selectinload(SOAPNote.icd_codes), selectinload(SOAPNote.cpt_codes))
        .where(SOAPNote.id == str(note_id))
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SOAP note not found")
    if current_user.role != UserRole.ADMIN and str(note.user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return note


def _decrypt_note(note: SOAPNote, session: RecordingSession | None = None, patient_name: str | None = None) -> SOAPNoteRead:
    """Decrypt encrypted SOAP sections and build schema response."""
    enc = get_phi_encryption()
    physician_edits = note.physician_edits or {}

    def _section(section_type: str, encrypted_text: str | None) -> dict:
        raw = enc.decrypt(encrypted_text) if encrypted_text else ""
        edit_meta = physician_edits.get(section_type, {})
        is_modified = section_type in physician_edits
        return {
            "type": section_type,
            "ai_generated_text": raw,
            "physician_edited_text": raw if is_modified else None,
            "is_modified": is_modified,
            "last_modified_at": edit_meta.get("changed_at"),
            "last_modified_by": edit_meta.get("by"),
        }

    subj = enc.decrypt(note.subjective) if note.subjective else None
    obj = enc.decrypt(note.objective) if note.objective else None
    asmt = enc.decrypt(note.assessment) if note.assessment else None
    plan = enc.decrypt(note.plan) if note.plan else None

    return SOAPNoteRead(
        id=note.id,
        session_id=note.session_id,
        user_id=note.user_id,
        patient_name=patient_name,
        patient_mrn=enc.decrypt(note.patient_mrn) if note.patient_mrn else None,
        encounter_id=session.encounter_id if session else None,
        status=note.status.value,
        subjective=subj,
        objective=obj,
        assessment=asmt,
        plan=plan,
        sections={
            "subjective": _section("subjective", note.subjective),
            "objective": _section("objective", note.objective),
            "assessment": _section("assessment", note.assessment),
            "plan": _section("plan", note.plan),
        },
        specialty=note.specialty,
        icd_codes=[
            ICDCodeItem(
                code=icd.code,
                description=icd.description,
                confidence=icd.confidence,
                is_primary=icd.is_primary,
            )
            for icd in (note.icd_codes or [])
        ],
        cpt_codes=[
            CPTCodeItem(
                code=cpt.code,
                description=cpt.description,
                confidence=cpt.confidence,
            )
            for cpt in (note.cpt_codes or [])
        ],
        approved_at=note.approved_at,
        fhir_push_status=note.fhir_push_status,
        fhir_resource_id=note.fhir_resource_id,
        expires_at=note.expires_at,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@router.get(
    "/{note_id}",
    response_model=SOAPNoteRead,
    summary="Get SOAP note",
    description="Retrieve a decrypted SOAP note with ICD-10 and CPT codes. Audit-logged.",
)
async def get_note(
    note_id: uuid.UUID,
    request: Request,
    current_user: ClinicalStaff,
    db: DB,
) -> SOAPNoteRead:
    """Get a SOAP note by UUID. Decrypts all PHI fields. Audit-logged."""
    note = await _get_note_with_codes(db, note_id, current_user)

    # Check expiry
    if note.expires_at and datetime.now(timezone.utc) > note.expires_at.replace(tzinfo=timezone.utc):
        if note.status == NoteStatus.DRAFT:
            note.status = NoteStatus.EXPIRED
            await db.commit()

    enc = get_phi_encryption()
    patient_mrn = enc.decrypt(note.patient_mrn) if note.patient_mrn else None

    await AuditService.log_phi_access(
        db=db,
        user_id=str(current_user.id),
        resource_type="SOAPNote",
        resource_id=str(note_id),
        patient_mrn=patient_mrn,
        ip_address=get_client_ip(request),
        action=AuditAction.VIEW_NOTE,
    )

    # Fetch session for encounter_id and patient name
    session_result = await db.execute(
        select(RecordingSession).where(RecordingSession.id == str(note.session_id))
    )
    session = session_result.scalar_one_or_none()

    # Resolve patient name from Patient table
    resolved_name: str | None = None
    if patient_mrn:
        try:
            settings = get_settings()
            hmac_val = compute_hmac(patient_mrn, settings.ENCRYPTION_KEY or "")
            p_result = await db.execute(
                select(Patient.enc_first_name, Patient.enc_last_name)
                .where(Patient.mrn_hmac == hmac_val)
            )
            p_row = p_result.first()
            if p_row:
                fn = enc.decrypt(p_row.enc_first_name) if p_row.enc_first_name else ""
                ln = enc.decrypt(p_row.enc_last_name) if p_row.enc_last_name else ""
                resolved_name = f"{fn} {ln}".strip() or None
        except Exception:
            pass

    return _decrypt_note(note, session=session, patient_name=resolved_name)


@router.patch(
    "/{note_id}",
    response_model=SOAPNoteRead,
    summary="Edit SOAP note sections",
    description=(
        "Apply physician edits to draft SOAP note sections. "
        "Cannot edit APPROVED or EXPIRED notes. Changes tracked in physician_edits."
    ),
)
async def edit_note(
    note_id: uuid.UUID,
    body: SOAPNoteEdit,
    request: Request,
    current_user: ClinicalStaff,
    db: DB,
) -> SOAPNoteRead:
    """
    Update SOAP note sections with physician corrections.

    Tracks edits as a JSON diff in physician_edits field.
    """
    note = await _get_note_with_codes(db, note_id, current_user)

    if note.status == NoteStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot edit an approved note",
        )
    if note.status == NoteStatus.EXPIRED:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Note has expired and cannot be edited",
        )

    enc = get_phi_encryption()
    update_data = body.model_dump(exclude_unset=True)
    edits: dict = {}

    for section in ("subjective", "objective", "assessment", "plan"):
        if section in update_data and update_data[section] is not None:
            edits[section] = {
                "changed_at": datetime.now(timezone.utc).isoformat(),
                "by": str(current_user.id),
            }
            setattr(note, section, enc.encrypt(update_data[section]))

    if edits:
        current_edits = note.physician_edits or {}
        current_edits.update(edits)
        note.physician_edits = current_edits

    # Replace ICD codes if provided
    if "icd_codes" in update_data and update_data["icd_codes"] is not None:
        for existing in list(note.icd_codes):
            await db.delete(existing)
        for item in update_data["icd_codes"]:
            db.add(ICDCode(
                note_id=note.id,
                code=item["code"],
                description=item["description"],
                confidence=item.get("confidence"),
                is_primary=item.get("is_primary", False),
            ))

    # Replace CPT codes if provided
    if "cpt_codes" in update_data and update_data["cpt_codes"] is not None:
        for existing in list(note.cpt_codes):
            await db.delete(existing)
        for item in update_data["cpt_codes"]:
            db.add(CPTCode(
                note_id=note.id,
                code=item["code"],
                description=item["description"],
                confidence=item.get("confidence"),
            ))

    edited_keys = list(edits.keys())
    if "icd_codes" in update_data:
        edited_keys.append("icd_codes")
    if "cpt_codes" in update_data:
        edited_keys.append("cpt_codes")

    enc = get_phi_encryption()
    patient_mrn_plain = enc.decrypt(note.patient_mrn) if note.patient_mrn else None

    await AuditService.log(
        db=db,
        action=AuditAction.EDIT_NOTE,
        user_id=str(current_user.id),
        resource_type="SOAPNote",
        resource_id=str(note_id),
        patient_mrn=patient_mrn_plain,
        ip_address=get_client_ip(request),
        details=f"Edited sections: {edited_keys}",
    )
    await db.commit()
    await db.refresh(note)

    # Reload with codes
    note = await _get_note_with_codes(db, note_id, current_user)
    return _decrypt_note(note)


@router.post(
    "/{note_id}/approve",
    response_model=SOAPNoteRead,
    summary="Approve SOAP note",
    description=(
        "Physician approval/signature of a draft SOAP note. "
        "Triggers audio deletion (zero-retention) and marks note as APPROVED. "
        "Approved notes can be pushed to EHR via /fhir/push/{note_id}."
    ),
)
async def approve_note(
    note_id: uuid.UUID,
    body: ApproveRequest,
    request: Request,
    current_user: CurrentUser,
    db: DB,
) -> SOAPNoteRead:
    """
    Approve a SOAP note after physician review.

    Only physicians and admins can approve notes.
    Triggers audio deletion from Redis (zero-retention policy).
    """
    if current_user.role not in (UserRole.PHYSICIAN, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only physicians and admins can approve SOAP notes",
        )

    note = await _get_note_with_codes(db, note_id, current_user)

    if note.status == NoteStatus.APPROVED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Note is already approved")
    if note.status == NoteStatus.EXPIRED:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Note has expired")

    now = datetime.now(timezone.utc)
    note.status = NoteStatus.APPROVED
    note.approved_at = now
    note.approved_by = current_user.id

    # Zero-retention: delete audio from Redis
    try:
        from app.config import get_settings
        import redis.asyncio as aioredis
        settings = get_settings()
        redis_client = aioredis.from_url(settings.REDIS_URL)
        audio_key = f"audio:{note.session_id}"
        await redis_client.delete(audio_key)
        await redis_client.aclose()

        # Mark audio as deleted in session record
        session_result = await db.execute(
            select(RecordingSession).where(RecordingSession.id == str(note.session_id))
        )
        session = session_result.scalar_one_or_none()
        if session and not session.audio_deleted_at:
            session.audio_deleted_at = now
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Audio deletion on approval failed: %s", exc)

    enc = get_phi_encryption()
    patient_mrn = enc.decrypt(note.patient_mrn) if note.patient_mrn else None

    await AuditService.log(
        db=db,
        action=AuditAction.APPROVE_NOTE,
        user_id=str(current_user.id),
        resource_type="SOAPNote",
        resource_id=str(note_id),
        patient_mrn=patient_mrn,
        ip_address=get_client_ip(request),
        details=f"Attestation: {body.attestation[:200]}",
    )
    await db.commit()

    note = await _get_note_with_codes(db, note_id, current_user)
    return _decrypt_note(note)


@router.post(
    "/{note_id}/generate",
    response_model=SOAPNoteRead,
    summary="Re-generate SOAP note from transcript",
    description="Trigger fresh AI SOAP note generation from the existing transcript.",
)
async def regenerate_note(
    note_id: uuid.UUID,
    body: SOAPGenerateRequest,
    request: Request,
    current_user: ClinicalStaff,
    db: DB,
) -> SOAPNoteRead:
    """
    Regenerate the SOAP note using a new specialty template or additional context.

    Only works on DRAFT or EXPIRED notes. Approved notes cannot be regenerated.
    """
    note = await _get_note_with_codes(db, note_id, current_user)

    if note.status == NoteStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot regenerate an approved note",
        )

    # Enqueue regeneration via Celery
    try:
        from app.workers.note_tasks import generate_soap_note
        generate_soap_note.apply_async(
            args=[str(note.session_id), body.specialty],
            countdown=0,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to enqueue SOAP regeneration: {exc}",
        )

    enc = get_phi_encryption()
    patient_mrn_plain = enc.decrypt(note.patient_mrn) if note.patient_mrn else None

    await AuditService.log(
        db=db,
        action=AuditAction.CREATE_NOTE,
        user_id=str(current_user.id),
        resource_type="SOAPNote",
        resource_id=str(note_id),
        patient_mrn=patient_mrn_plain,
        ip_address=get_client_ip(request),
        details=f"Regeneration requested with specialty={body.specialty}",
    )

    return _decrypt_note(note)
