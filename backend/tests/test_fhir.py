from __future__ import annotations
"""
ClinNote AI — FHIR Integration Tests
=======================================
Tests for:
  - FHIRService.build_document_reference resource structure
  - FHIRService.build_diagnostic_report resource structure
  - FHIR push API (mocked HTTP)
  - FHIR status check
"""


import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.fhir_service import FHIRService


class TestFHIRResourceBuilders:
    """Unit tests for FHIR resource construction."""

    def setup_method(self):
        """Set up FHIRService instance."""
        self.svc = FHIRService()

    def test_build_document_reference_structure(self) -> None:
        """DocumentReference should have required FHIR R4 fields."""
        doc_ref = self.svc.build_document_reference(
            note_id="test-note-id",
            patient_fhir_id="Patient/12345",
            encounter_fhir_id="Encounter/67890",
            subjective="Patient presents with sore throat",
            objective="Temp 38.2C, pharynx erythematous",
            assessment="Acute pharyngitis J02.9",
            plan="Rapid strep test, acetaminophen",
            authored_date=datetime.now(timezone.utc),
        )

        assert doc_ref["resourceType"] == "DocumentReference"
        assert doc_ref["status"] == "current"
        assert doc_ref["docStatus"] == "final"
        assert "type" in doc_ref
        assert "subject" in doc_ref
        assert doc_ref["subject"]["reference"] == "Patient/12345"
        assert "content" in doc_ref
        assert len(doc_ref["content"]) == 1
        assert "context" in doc_ref
        assert doc_ref["context"]["encounter"][0]["reference"] == "Encounter/67890"

        # Verify content is base64 encoded
        import base64
        attachment = doc_ref["content"][0]["attachment"]
        decoded = base64.b64decode(attachment["data"]).decode("utf-8")
        assert "SUBJECTIVE:" in decoded
        assert "Patient presents with sore throat" in decoded

    def test_build_document_reference_without_encounter(self) -> None:
        """DocumentReference without encounter should not have context."""
        doc_ref = self.svc.build_document_reference(
            note_id="test-note-id",
            patient_fhir_id="Patient/12345",
            encounter_fhir_id=None,
            subjective="Test S",
            objective="Test O",
            assessment="Test A",
            plan="Test P",
        )
        assert "context" not in doc_ref

    def test_build_diagnostic_report_structure(self) -> None:
        """DiagnosticReport should have required FHIR R4 fields and codes."""
        # Create mock ICD codes
        icd1 = MagicMock()
        icd1.code = "J02.9"
        icd1.description = "Acute pharyngitis, unspecified"

        icd2 = MagicMock()
        icd2.code = "I10"
        icd2.description = "Essential hypertension"

        diag_report = self.svc.build_diagnostic_report(
            note_id="test-note-id",
            patient_fhir_id="Patient/12345",
            encounter_fhir_id="Encounter/67890",
            icd_codes=[icd1, icd2],
            authored_date=datetime.now(timezone.utc),
        )

        assert diag_report["resourceType"] == "DiagnosticReport"
        assert diag_report["status"] == "final"
        assert diag_report["subject"]["reference"] == "Patient/12345"
        assert len(diag_report["conclusionCode"]) == 2
        assert diag_report["conclusionCode"][0]["coding"][0]["code"] == "J02.9"
        assert "J02.9" in diag_report["conclusion"]

    def test_icd10_coding_system(self) -> None:
        """Diagnostic codes should use ICD-10-CM FHIR coding system."""
        icd = MagicMock()
        icd.code = "E11.9"
        icd.description = "Type 2 diabetes mellitus"

        diag_report = self.svc.build_diagnostic_report(
            note_id="test",
            patient_fhir_id="Patient/1",
            encounter_fhir_id=None,
            icd_codes=[icd],
        )

        coding_system = diag_report["conclusionCode"][0]["coding"][0]["system"]
        assert "icd-10" in coding_system.lower() or "icd10" in coding_system.lower()

    def test_document_reference_loinc_type(self) -> None:
        """DocumentReference type should use LOINC code for progress note."""
        doc_ref = self.svc.build_document_reference(
            note_id="test",
            patient_fhir_id="Patient/1",
            encounter_fhir_id=None,
            subjective="S",
            objective="O",
            assessment="A",
            plan="P",
        )

        type_coding = doc_ref["type"]["coding"][0]
        assert type_coding["system"] == "http://loinc.org"
        assert type_coding["code"] == "11506-3"


@pytest.mark.asyncio
class TestFHIRPushAPI:
    """Integration tests for FHIR push API endpoints."""

    async def test_fhir_status_unauthenticated(
        self,
        async_client,
    ) -> None:
        """Unauthenticated access to FHIR status should return 401."""
        from httpx import AsyncClient
        fake_id = str(uuid.uuid4())
        response = await async_client.get(f"/api/v1/fhir/status/{fake_id}")
        assert response.status_code == 401

    async def test_fhir_status_nonexistent_note(
        self,
        async_client,
        physician_token: str,
    ) -> None:
        """FHIR status for non-existent note should return 404."""
        from httpx import AsyncClient
        fake_id = str(uuid.uuid4())
        response = await async_client.get(
            f"/api/v1/fhir/status/{fake_id}",
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert response.status_code == 404
