from __future__ import annotations
"""
ClinNote AI — HL7 FHIR R4 Integration Service
================================================
Pushes approved SOAP notes to EHR systems as FHIR R4 resources.

Resources created:
  - DocumentReference : Full SOAP note content as base64-encoded text
  - DiagnosticReport  : ICD-10 diagnosis codes linked to the encounter

Retry policy: up to 5 attempts with exponential backoff.

HIPAA Note:
  FHIR payloads contain PHI (SOAP note text, patient ID).
  All transmission is over TLS. Access tokens are short-lived OAuth2.
  Each push is recorded in the AuditLog.
"""


import asyncio
import base64
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

FHIR_MAX_RETRIES = 5


class FHIRService:
    """
    HL7 FHIR R4 push client.

    Usage:
        svc = FHIRService()
        result = await svc.push_note_to_ehr(note, fhir_config)
    """

    def __init__(self) -> None:
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(30.0))

    async def __aenter__(self) -> "FHIRService":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self._http.aclose()

    # ------------------------------------------------------------------ #
    # Main entry point
    # ------------------------------------------------------------------ #

    async def push_note_to_ehr(
        self,
        note: Any,        # SOAPNote ORM object (type hint relaxed to avoid circular import)
        fhir_config: Any,  # EHRIntegration ORM object
        fhir_patient_id: str,
        fhir_encounter_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Push an approved SOAP note to the configured EHR via FHIR R4.

        Args:
            note              : SOAPNote ORM object (status must be APPROVED).
            fhir_config       : EHRIntegration ORM object with FHIR endpoint config.
            fhir_patient_id   : FHIR Patient resource ID in the target EHR.
            fhir_encounter_id : Optional FHIR Encounter ID to link to.

        Returns:
            dict with keys:
              - status         : "success" | "failed"
              - fhir_resource_id: DocumentReference ID created in EHR.
              - document_url   : Full URL to the created DocumentReference.
              - message        : Human-readable result message.
              - timestamp      : Push timestamp ISO string.

        Raises:
            RuntimeError: If all FHIR_MAX_RETRIES attempts fail.
        """
        # Decrypt note content for FHIR payload
        from app.utils.encryption import get_phi_encryption
        enc = get_phi_encryption()

        subjective = enc.decrypt(note.subjective) or ""
        objective = enc.decrypt(note.objective) or ""
        assessment = enc.decrypt(note.assessment) or ""
        plan = enc.decrypt(note.plan) or ""

        # Build FHIR resources
        doc_ref = self.build_document_reference(
            note_id=str(note.id),
            patient_fhir_id=fhir_patient_id,
            encounter_fhir_id=fhir_encounter_id,
            subjective=subjective,
            objective=objective,
            assessment=assessment,
            plan=plan,
            authored_date=note.approved_at or note.created_at,
        )

        token = await self._get_access_token(fhir_config)
        base_url = fhir_config.fhir_base_url.rstrip("/")
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/fhir+json",
            "Accept": "application/fhir+json",
        }

        # POST DocumentReference
        doc_ref_id, doc_ref_url = await self._post_fhir_resource(
            url=f"{base_url}/DocumentReference",
            resource=doc_ref,
            headers=headers,
        )

        # POST DiagnosticReport for ICD codes (if any)
        if note.icd_codes:
            diag_report = self.build_diagnostic_report(
                note_id=str(note.id),
                patient_fhir_id=fhir_patient_id,
                encounter_fhir_id=fhir_encounter_id,
                icd_codes=note.icd_codes,
                authored_date=note.approved_at or note.created_at,
            )
            try:
                await self._post_fhir_resource(
                    url=f"{base_url}/DiagnosticReport",
                    resource=diag_report,
                    headers=headers,
                )
            except Exception as exc:
                logger.warning("DiagnosticReport push failed (non-fatal): %s", exc)

        logger.info(
            "FHIR push success: DocumentReference/%s for note %s", doc_ref_id, note.id
        )
        return {
            "status": "success",
            "fhir_resource_id": f"DocumentReference/{doc_ref_id}",
            "document_url": doc_ref_url,
            "message": f"Successfully pushed to EHR. DocumentReference/{doc_ref_id}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------ #
    # FHIR resource builders
    # ------------------------------------------------------------------ #

    def build_document_reference(
        self,
        note_id: str,
        patient_fhir_id: str,
        encounter_fhir_id: str | None,
        subjective: str,
        objective: str,
        assessment: str,
        plan: str,
        authored_date: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Build a FHIR R4 DocumentReference resource for a SOAP note.

        Args:
            note_id          : Internal note UUID.
            patient_fhir_id  : FHIR Patient resource reference (e.g. "Patient/12345").
            encounter_fhir_id: FHIR Encounter reference (optional).
            subjective        : S section plain text.
            objective         : O section plain text.
            assessment        : A section plain text.
            plan              : P section plain text.
            authored_date     : When the note was authored.

        Returns:
            FHIR R4 DocumentReference resource dict.
        """
        soap_text = (
            f"SUBJECTIVE:\n{subjective}\n\n"
            f"OBJECTIVE:\n{objective}\n\n"
            f"ASSESSMENT:\n{assessment}\n\n"
            f"PLAN:\n{plan}"
        )
        encoded_content = base64.b64encode(soap_text.encode("utf-8")).decode("utf-8")
        authored = (authored_date or datetime.now(timezone.utc)).isoformat()

        resource: dict[str, Any] = {
            "resourceType": "DocumentReference",
            "id": str(uuid4()),
            "status": "current",
            "docStatus": "final",
            "type": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "11506-3",
                        "display": "Progress note",
                    }
                ]
            },
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://hl7.org/fhir/us/core/CodeSystem/us-core-documentreference-category",
                            "code": "clinical-note",
                            "display": "Clinical Note",
                        }
                    ]
                }
            ],
            "subject": {"reference": patient_fhir_id},
            "date": authored,
            "author": [
                {
                    "display": "ClinNote AI",
                    "extension": [
                        {
                            "url": "http://clinnote.ai/fhir/Extension/generated-by",
                            "valueString": "ClinNote AI v1.0.0",
                        }
                    ],
                }
            ],
            "content": [
                {
                    "attachment": {
                        "contentType": "text/plain; charset=utf-8",
                        "data": encoded_content,
                        "title": f"SOAP Note - {note_id}",
                        "creation": authored,
                    },
                    "format": {
                        "system": "http://ihe.net/fhir/ihe.formatcode.fhir/CodeSystem/formatcode",
                        "code": "urn:ihe:iti:xds-sd:text:2008",
                        "display": "Plain Text",
                    },
                }
            ],
            "extension": [
                {
                    "url": "http://clinnote.ai/fhir/Extension/note-id",
                    "valueString": note_id,
                }
            ],
        }

        if encounter_fhir_id:
            resource["context"] = {
                "encounter": [{"reference": encounter_fhir_id}]
            }

        return resource

    def build_diagnostic_report(
        self,
        note_id: str,
        patient_fhir_id: str,
        encounter_fhir_id: str | None,
        icd_codes: list,
        authored_date: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Build a FHIR R4 DiagnosticReport resource for ICD-10 diagnosis codes.

        Args:
            note_id          : Internal note UUID.
            patient_fhir_id  : FHIR Patient resource reference.
            encounter_fhir_id: FHIR Encounter reference (optional).
            icd_codes         : List of ICDCode ORM objects.
            authored_date     : Report effective date.

        Returns:
            FHIR R4 DiagnosticReport resource dict.
        """
        authored = (authored_date or datetime.now(timezone.utc)).isoformat()

        coded_diagnoses = []
        for icd in icd_codes:
            coded_diagnoses.append({
                "coding": [
                    {
                        "system": "http://hl7.org/fhir/sid/icd-10-cm",
                        "code": icd.code,
                        "display": icd.description,
                    }
                ],
                "text": icd.description,
            })

        resource: dict[str, Any] = {
            "resourceType": "DiagnosticReport",
            "id": str(uuid4()),
            "status": "final",
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                            "code": "HM",
                            "display": "Hematology",
                        }
                    ]
                }
            ],
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "11524-6",
                        "display": "EKG impression",
                    }
                ],
                "text": "Clinical Assessment",
            },
            "subject": {"reference": patient_fhir_id},
            "effectiveDateTime": authored,
            "issued": authored,
            "conclusion": " | ".join(f"{icd.code}: {icd.description}" for icd in icd_codes),
            "conclusionCode": coded_diagnoses,
            "extension": [
                {
                    "url": "http://clinnote.ai/fhir/Extension/note-id",
                    "valueString": note_id,
                }
            ],
        }

        if encounter_fhir_id:
            resource["encounter"] = {"reference": encounter_fhir_id}

        return resource

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    async def _get_access_token(self, fhir_config: Any) -> str:
        """
        Obtain an OAuth2 access token for the FHIR endpoint.

        For EHR systems with a token endpoint, performs client_credentials grant.
        Falls back to returning client_id as a bearer token for systems that
        use API key auth (e.g. test sandboxes).

        Args:
            fhir_config: EHRIntegration ORM object.

        Returns:
            Access token string.
        """
        if not fhir_config.token_endpoint:
            # API-key style auth (return client_id or empty)
            return fhir_config.client_id or ""

        from app.utils.encryption import get_phi_encryption
        enc = get_phi_encryption()
        client_secret = enc.decrypt(fhir_config.client_secret) if fhir_config.client_secret else ""

        response = await self._http.post(
            fhir_config.token_endpoint,
            data={
                "grant_type": "client_credentials",
                "client_id": fhir_config.client_id,
                "client_secret": client_secret,
                "scope": "system/DocumentReference.write system/DiagnosticReport.write",
            },
        )
        response.raise_for_status()
        return response.json().get("access_token", "")

    async def _post_fhir_resource(
        self,
        url: str,
        resource: dict[str, Any],
        headers: dict[str, str],
    ) -> tuple[str, str]:
        """
        POST a FHIR resource to the server with exponential retry.

        Args:
            url     : Full FHIR endpoint URL.
            resource: FHIR resource dict.
            headers : Auth and content headers.

        Returns:
            Tuple of (resource_id, resource_url).

        Raises:
            RuntimeError: After FHIR_MAX_RETRIES exhausted.
        """
        last_exc: Exception | None = None

        for attempt in range(1, FHIR_MAX_RETRIES + 1):
            try:
                resp = await self._http.post(url, json=resource, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                resource_id = data.get("id", "")
                location = resp.headers.get("Location", f"{url}/{resource_id}")
                return resource_id, location

            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "FHIR POST %s failed attempt %d/%d: HTTP %s",
                    url, attempt, FHIR_MAX_RETRIES, exc.response.status_code,
                )
                last_exc = exc
                if exc.response.status_code in (400, 401, 403, 422):
                    raise  # Non-retryable
                if attempt < FHIR_MAX_RETRIES:
                    await asyncio.sleep(2.0 ** attempt)

            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                logger.warning("FHIR connection error attempt %d/%d: %s", attempt, FHIR_MAX_RETRIES, exc)
                last_exc = exc
                if attempt < FHIR_MAX_RETRIES:
                    await asyncio.sleep(2.0 ** attempt)

        raise RuntimeError(
            f"FHIR push to {url} failed after {FHIR_MAX_RETRIES} attempts: {last_exc}"
        )
