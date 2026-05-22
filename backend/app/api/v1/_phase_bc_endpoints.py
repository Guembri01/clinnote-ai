"""Phase B + C endpoint module for project_03_clinnote_ai.

Side-loaded module — attaches decorators to the existing notes.router so
no central route table edit is needed. MUST be imported before
`api_router.include_router(notes.router)` in router.py so the routes are
present at include time.

Phase A is already complete in this project (DeepInfra Whisper Large v3 via
`app/services/transcription_service.py`). This module only adds the
voice ↔ SOAP cross-validation audit + clinical-QA brief PDF.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List

from fastapi import Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.v1.deps import CurrentUser, DB
from app.api.v1.notes import router
from app.models.recording_session import RecordingSession
from app.models.soap_note import SOAPNote
from app.models.transcript import Transcript
from app.models.user import UserRole
from app.services.clinical_qa_analyzer import ClinicalQAAnalyzer
from app.services.clinical_qa_brief_pdf_service import (
    render_clinical_qa_brief_pdf, safe_pdf_filename,
)
from app.utils.encryption import get_phi_encryption


async def _gather_qa_audit(note_id: uuid.UUID, db, current_user):
    note_q = await db.execute(
        select(SOAPNote)
        .options(selectinload(SOAPNote.icd_codes), selectinload(SOAPNote.cpt_codes))
        .where(SOAPNote.id == str(note_id))
    )
    note = note_q.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SOAP note not found")
    if current_user.role != UserRole.ADMIN and str(note.user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Pull the associated transcript via session
    transcript_text = ""
    trans_q = await db.execute(
        select(Transcript).where(Transcript.session_id == note.session_id)
    )
    trans = trans_q.scalar_one_or_none()
    enc = get_phi_encryption()
    if trans:
        if trans.corrected_text:
            transcript_text = enc.decrypt(trans.corrected_text) or ""
        elif trans.raw_text:
            transcript_text = enc.decrypt(trans.raw_text) or ""

    note_dict: Dict[str, Any] = {
        "id": str(note.id),
        "session_id": str(note.session_id),
        "status": note.status.value if hasattr(note.status, "value") else str(note.status),
        "specialty": note.specialty,
        "subjective": enc.decrypt(note.subjective) if note.subjective else "",
        "objective": enc.decrypt(note.objective) if note.objective else "",
        "assessment": enc.decrypt(note.assessment) if note.assessment else "",
        "plan": enc.decrypt(note.plan) if note.plan else "",
        "icd_codes": [
            {"code": c.code, "description": c.description, "is_primary": c.is_primary}
            for c in (note.icd_codes or [])
        ],
        "cpt_codes": [
            {"code": c.code, "description": c.description}
            for c in (note.cpt_codes or [])
        ],
    }

    analyzer = ClinicalQAAnalyzer()
    result = await analyzer.analyze(transcript_text, note_dict)
    return note, note_dict, transcript_text, result


@router.get("/{note_id}/transcript")
async def get_note_transcript(
    note_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
):
    """Phase E — return the decrypted Transcript for the SOAP note's session."""
    note_q = await db.execute(select(SOAPNote).where(SOAPNote.id == str(note_id)))
    note = note_q.scalar_one_or_none()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="SOAP note not found"
        )
    if current_user.role != UserRole.ADMIN and str(note.user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    trans_q = await db.execute(
        select(Transcript).where(Transcript.session_id == note.session_id)
    )
    trans = trans_q.scalar_one_or_none()
    if not trans:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not yet available for this note.",
        )

    enc = get_phi_encryption()
    voice_transcript = enc.decrypt(trans.raw_text or trans.corrected_text) or ""
    return [
        {
            "id": str(trans.id),
            "session_id": str(trans.session_id),
            "voice_transcript": voice_transcript,
            "transcript_status": "completed" if voice_transcript else "pending",
            "provider": "deepinfra-whisper-large-v3",
            "language": trans.language,
            "confidence": trans.confidence,
            "word_count": trans.word_count,
            "created_at": trans.created_at.isoformat() if trans.created_at else None,
        }
    ]


@router.post("/{note_id}/voice-audit")
async def voice_clinical_qa_audit(
    note_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
):
    _, note_dict, transcript, result = await _gather_qa_audit(note_id, db, current_user)
    return {
        "status": "completed" if transcript else "no_transcript",
        "mode": result.get("mode"),
        "note_id": str(note_id),
        "transcript_excerpt": (transcript or "")[:500],
        "voice_signals": result.get("voice_signals", {}),
        "voice_medications": result.get("voice_medications", []),
        "voice_allergies": result.get("voice_allergies", []),
        "voice_vitals": result.get("voice_vitals", {}),
        "voice_icd_codes": result.get("voice_icd_codes", []),
        "voice_cpt_codes": result.get("voice_cpt_codes", []),
        "missing_meds_in_plan": result.get("missing_meds_in_plan", []),
        "missing_allergies_in_note": result.get("missing_allergies_in_note", []),
        "missing_vitals_in_objective": result.get("missing_vitals_in_objective", []),
        "uncoded_icd": result.get("uncoded_icd", []),
        "uncoded_cpt": result.get("uncoded_cpt", []),
        "critical_unescalated": result.get("critical_unescalated", []),
        "decision": result.get("decision"),
        "talking_points": result.get("talking_points", []),
    }


@router.get("/{note_id}/clinical-qa-brief.pdf")
async def clinical_qa_brief_pdf(
    note_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
):
    _, note_dict, transcript, result = await _gather_qa_audit(note_id, db, current_user)
    pdf_bytes = render_clinical_qa_brief_pdf(
        soap_note=note_dict,
        transcript=transcript or None,
        voice_signals=result.get("voice_signals", {}),
        voice_medications=result.get("voice_medications", []),
        voice_allergies=result.get("voice_allergies", []),
        voice_vitals=result.get("voice_vitals", {}),
        voice_icd_codes=result.get("voice_icd_codes", []),
        voice_cpt_codes=result.get("voice_cpt_codes", []),
        missing_meds_in_plan=result.get("missing_meds_in_plan", []),
        missing_allergies_in_note=result.get("missing_allergies_in_note", []),
        missing_vitals_in_objective=result.get("missing_vitals_in_objective", []),
        uncoded_icd=result.get("uncoded_icd", []),
        uncoded_cpt=result.get("uncoded_cpt", []),
        critical_unescalated=result.get("critical_unescalated", []),
        decision=result.get("decision", "unspecified"),
        talking_points=result.get("talking_points", []),
        generated_by=getattr(current_user, "email", None) or str(current_user.id),
    )
    filename = safe_pdf_filename(str(note_id))
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-ClinNote-Mode": result.get("mode", "unknown"),
            "X-ClinNote-Decision": str(result.get("decision", "unspecified")),
            "X-ClinNote-Critical": str(len(result.get("critical_unescalated", []))),
            "X-ClinNote-Missing-Allergies": str(len(result.get("missing_allergies_in_note", []))),
        },
    )
