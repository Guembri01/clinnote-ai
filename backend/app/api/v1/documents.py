from __future__ import annotations
"""
ClinNote AI — Documents API (OCR)
=====================================
Endpoints:
  POST /documents/upload — Upload and OCR a lab report or intake form

Supports PDF, PNG, JPEG, TIFF up to 10MB.
Extracted data is returned for integration into SOAP note generation.

HIPAA Note:
  Document bytes are sent to Azure Document Intelligence under BAA.
  No raw document bytes are stored by this application.
"""


from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status

from app.api.v1.deps import ClinicalStaff, DB, get_client_ip
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.services.ocr_service import OCRService

router = APIRouter(prefix="/documents", tags=["Documents"])

SUPPORTED_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/tiff",
}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post(
    "/upload",
    summary="Upload and OCR a clinical document",
    description=(
        "Upload a lab report, intake form, or other clinical document for OCR extraction. "
        "Supported formats: PDF, PNG, JPEG, TIFF. Maximum size: 10MB. "
        "Returns structured extracted data (lab values, vitals, medications, allergies)."
    ),
)
async def upload_document(
    request: Request,
    current_user: ClinicalStaff,
    db: DB,
    file: UploadFile = File(..., description="Lab report or intake form file"),
    document_type: str = Form(
        default="lab_report",
        description="Type of document: lab_report | intake_form | other",
    ),
    session_id: str | None = Form(
        default=None,
        description="Optional recording session ID to associate this document with",
    ),
) -> dict:
    """
    OCR extract data from an uploaded clinical document.

    Args:
        file         : Uploaded file (PDF/image).
        document_type: Type of document for parsing strategy.
        session_id   : Optional session UUID to associate lab data with.

    Returns:
        Extracted data dict appropriate to document_type:
          - lab_report  : {lab_values, raw_text, page_count, confidence}
          - intake_form : {vitals, medications, allergies, chief_complaint, raw_text}
          - other       : {raw_text}

    Raises:
        400: If file type is unsupported or file is too large.
        503: If Azure Document Intelligence is unavailable.
    """
    # Validate content type
    content_type = file.content_type or ""
    if content_type not in SUPPORTED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {content_type}. Supported: {', '.join(SUPPORTED_CONTENT_TYPES)}",
        )

    # Read and validate size
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large: {len(file_bytes):,} bytes. Maximum: {MAX_FILE_SIZE_BYTES:,} bytes",
        )

    await AuditService.log(
        db=db,
        action=AuditAction.UPLOAD_DOCUMENT,
        user_id=str(current_user.id),
        resource_type="Document",
        ip_address=get_client_ip(request),
        details=f"type={document_type} file={file.filename} size={len(file_bytes)} session={session_id}",
    )

    # Process with OCR
    svc = OCRService()

    try:
        if document_type == "lab_report":
            result = await svc.extract_lab_report(file_bytes, file.filename or "document.pdf")
        elif document_type == "intake_form":
            result = await svc.process_intake_form(file_bytes)
        else:
            text = await svc.extract_document_text(file_bytes)
            result = {"raw_text": text}

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Document Intelligence service error: {type(exc).__name__}: {str(exc)[:200]}",
        )

    return {
        "document_type": document_type,
        "filename": file.filename,
        "file_size_bytes": len(file_bytes),
        "session_id": session_id,
        "extracted_data": result,
    }
