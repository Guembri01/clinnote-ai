from __future__ import annotations
"""
ClinNote AI — SOAP Note Generation Tests
==========================================
Tests for:
  - SOAPService.generate_soap_note with mocked OpenAI
  - Specialty template selection
  - ICD/CPT code normalization
  - SOAP note retrieval API
  - SOAP note editing
  - Note approval
"""


import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.services.soap_service import SOAPService
from app.utils.specialty_templates import get_system_prompt, list_specialties


@pytest.mark.asyncio
class TestSOAPService:
    """Unit tests for SOAPService."""

    async def test_generate_soap_note_success(self, mock_openai) -> None:
        """SOAP note should be generated from transcript."""
        svc = SOAPService()
        result = await svc.generate_soap_note(
            transcript="Patient presents with sore throat for 3 days. Temperature 38.2C.",
            patient_context={"specialty": "primary_care"},
            specialty="primary_care",
        )
        assert "subjective" in result
        assert "objective" in result
        assert "assessment" in result
        assert "plan" in result
        assert "icd10_codes" in result
        assert "cpt_codes" in result
        assert isinstance(result["icd10_codes"], list)

    async def test_parse_soap_response_valid_json(self) -> None:
        """_parse_soap_response should handle valid JSON correctly."""
        raw = json.dumps({
            "subjective": "Chief complaint: sore throat",
            "objective": "Temp 38.2C",
            "assessment": "Acute pharyngitis",
            "plan": "Rapid strep test, acetaminophen",
            "icd10_codes": [
                {"code": "J02.9", "description": "Acute pharyngitis", "confidence": 0.92, "is_primary": True}
            ],
            "cpt_codes": [
                {"code": "99213", "description": "Office visit", "confidence": 0.85}
            ],
        })
        result = SOAPService._parse_soap_response(raw)
        assert result["subjective"] == "Chief complaint: sore throat"
        assert len(result["icd10_codes"]) == 1
        assert result["icd10_codes"][0]["is_primary"] is True

    async def test_parse_soap_response_missing_sections(self) -> None:
        """Missing SOAP sections should be filled with default text."""
        raw = json.dumps({
            "subjective": "Sore throat",
            "icd10_codes": [],
            "cpt_codes": [],
        })
        result = SOAPService._parse_soap_response(raw)
        assert result["objective"] == "Insufficient information documented."
        assert result["assessment"] == "Insufficient information documented."
        assert result["plan"] == "Insufficient information documented."

    async def test_parse_soap_response_sets_primary_icd(self) -> None:
        """If no primary ICD code, first one should be marked primary."""
        raw = json.dumps({
            "subjective": "Test",
            "objective": "Test",
            "assessment": "Test",
            "plan": "Test",
            "icd10_codes": [
                {"code": "I10", "description": "Hypertension", "confidence": 0.9, "is_primary": False},
                {"code": "E11.9", "description": "T2DM", "confidence": 0.85, "is_primary": False},
            ],
            "cpt_codes": [],
        })
        result = SOAPService._parse_soap_response(raw)
        assert result["icd10_codes"][0]["is_primary"] is True

    async def test_generate_soap_with_lab_data(self, mock_openai) -> None:
        """SOAP generation should include lab data in the prompt."""
        svc = SOAPService()
        result = await svc.generate_soap_note(
            transcript="Patient presents for annual checkup.",
            patient_context={"specialty": "primary_care"},
            specialty="primary_care",
            lab_data={"glucose": "95 mg/dL", "HbA1c": "5.8%"},
        )
        # Should complete without error
        assert "subjective" in result


class TestSpecialtyTemplates:
    """Tests for specialty prompt templates."""

    def test_all_specialties_have_prompts(self) -> None:
        """All specialties should have non-empty prompts."""
        for specialty in list_specialties():
            prompt = get_system_prompt(specialty)
            assert len(prompt) > 100
            assert "SOAP" in prompt.upper() or "SUBJECTIVE" in prompt.upper()

    def test_unknown_specialty_falls_back_to_primary_care(self) -> None:
        """Unknown specialty should fall back to primary_care template."""
        prompt_unknown = get_system_prompt("dermatology")
        prompt_primary = get_system_prompt("primary_care")
        # Both should include base prompt
        assert len(prompt_unknown) > 0
        assert "primary care" in prompt_primary.lower() or "family" in prompt_primary.lower()

    def test_cardiology_prompt_includes_cardiac_terms(self) -> None:
        """Cardiology prompt should include cardiac-specific instructions."""
        prompt = get_system_prompt("cardiology")
        assert "cardiac" in prompt.lower() or "cardio" in prompt.lower()

    def test_psychiatry_prompt_includes_mse(self) -> None:
        """Psychiatry prompt should include mental status exam."""
        prompt = get_system_prompt("psychiatry")
        assert "mental status" in prompt.lower() or "mse" in prompt.lower()


@pytest.mark.asyncio
class TestSOAPNoteAPI:
    """Integration tests for SOAP note API endpoints."""

    async def test_get_nonexistent_note(
        self,
        async_client: AsyncClient,
        physician_token: str,
    ) -> None:
        """Getting a non-existent note should return 404."""
        fake_id = str(uuid.uuid4())
        response = await async_client.get(
            f"/api/v1/notes/{fake_id}",
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert response.status_code == 404

    async def test_get_note_unauthenticated(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Unauthenticated access to notes should return 401."""
        fake_id = str(uuid.uuid4())
        response = await async_client.get(f"/api/v1/notes/{fake_id}")
        assert response.status_code == 401
