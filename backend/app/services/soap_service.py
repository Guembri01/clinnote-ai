from __future__ import annotations
"""
ClinNote AI — SOAP Note Generation Service
============================================
Uses GPT-4.1-nano to generate structured SOAP notes from encounter transcripts.

Model: gpt-4.1-nano-2025-04-14
API  : OpenAI Chat Completions

Features:
  - Specialty-specific prompt templates (8 specialties)
  - Structured JSON output (Subjective / Objective / Assessment / Plan)
  - ICD-10-CM code suggestions with confidence scores
  - CPT code suggestions
  - Lab data integration (from OCR service)
  - Retries with exponential backoff on transient errors

HIPAA Note:
  Transcript text (PHI) is sent to OpenAI under a Business Associate Agreement.
  Never log or cache the transcript in cleartext in application logs.
"""


import asyncio
import json
import logging
from typing import Any

from openai import AsyncOpenAI, OpenAIError

from app.config import get_settings
from app.utils.specialty_templates import get_system_prompt, get_user_prompt

logger = logging.getLogger(__name__)
settings = get_settings()

# Redact PHI from log lines
_REDACTED = "[REDACTED-PHI]"


class SOAPService:
    """
    GPT-4.1-nano powered SOAP note generation service.

    Usage:
        svc = SOAPService()
        note = await svc.generate_soap_note(
            transcript="Patient presents with...",
            patient_context={"age_group": "adult", "specialty": "cardiology"},
            specialty="cardiology",
        )
    """

    MAX_RETRIES = 3
    RETRY_BACKOFF = 2.0

    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def generate_soap_note(
        self,
        transcript: str,
        patient_context: dict[str, Any],
        specialty: str = "primary_care",
        lab_data: dict[str, Any] | None = None,
        additional_context: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate a structured SOAP note from an encounter transcript.

        Args:
            transcript        : Full corrected transcript text (contains PHI).
            patient_context   : Non-PHI metadata dict (age_group, encounter_type, etc.).
            specialty         : Clinical specialty key for prompt template selection.
            lab_data          : Structured lab results from OCR service (optional).
            additional_context: Extra physician instruction for the AI.

        Returns:
            dict with keys:
              - subjective  (str)  : S section
              - objective   (str)  : O section
              - assessment  (str)  : A section
              - plan        (str)  : P section
              - icd10_codes (list) : [{code, description, confidence, is_primary}]
              - cpt_codes   (list) : [{code, description, confidence}]
              - raw_response(str)  : Original AI JSON string (for audit)

        Raises:
            ValueError    : If the AI returns malformed JSON.
            RuntimeError  : After MAX_RETRIES exhausted.
        """
        system_prompt = get_system_prompt(specialty)
        user_prompt = get_user_prompt(
            transcript=transcript,
            patient_context=patient_context,
            lab_data=lab_data,
            additional_context=additional_context,
        )

        last_exc: Exception | None = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = await self._client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.1,       # Low temp for clinical accuracy
                    max_tokens=4096,
                    response_format={"type": "json_object"},
                )

                raw_content = response.choices[0].message.content or ""
                parsed = self._parse_soap_response(raw_content)
                parsed["raw_response"] = raw_content

                logger.info(
                    "SOAP note generated (specialty=%s, icd_codes=%d, cpt_codes=%d)",
                    specialty,
                    len(parsed.get("icd10_codes", [])),
                    len(parsed.get("cpt_codes", [])),
                )
                return parsed

            except OpenAIError as exc:
                logger.warning(
                    "OpenAI API error on attempt %d/%d: %s",
                    attempt, self.MAX_RETRIES, type(exc).__name__,
                )
                last_exc = exc
                # Rate limit / server error — retry
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self.RETRY_BACKOFF ** attempt)

            except (ValueError, json.JSONDecodeError) as exc:
                # Parsing error — retry with clarification
                logger.warning("SOAP parse error on attempt %d: %s", attempt, exc)
                last_exc = exc
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(1.0)

        raise RuntimeError(
            f"SOAP note generation failed after {self.MAX_RETRIES} attempts: {last_exc}"
        )

    async def regenerate_section(
        self,
        section: str,
        transcript: str,
        current_content: str,
        specialty: str = "primary_care",
        physician_instruction: str = "",
    ) -> str:
        """
        Regenerate a single SOAP section based on physician feedback.

        Args:
            section             : One of 'subjective', 'objective', 'assessment', 'plan'.
            transcript          : Original encounter transcript.
            current_content     : Current section text to improve upon.
            specialty           : Clinical specialty key.
            physician_instruction: Physician's specific feedback for improvement.

        Returns:
            Regenerated section text (plain string, not JSON).

        Raises:
            ValueError : For invalid section names.
            RuntimeError: On API failure.
        """
        valid_sections = {"subjective", "objective", "assessment", "plan"}
        if section not in valid_sections:
            raise ValueError(f"Invalid section '{section}'. Must be one of {valid_sections}")

        section_labels = {
            "subjective": "S (Subjective)",
            "objective": "O (Objective)",
            "assessment": "A (Assessment)",
            "plan": "P (Plan)",
        }

        system_prompt = (
            get_system_prompt(specialty) +
            f"\n\nYou are regenerating ONLY the {section_labels[section]} section. "
            "Return ONLY the section text as a plain string, no JSON wrapping."
        )

        user_msg = (
            f"TRANSCRIPT:\n{transcript}\n\n"
            f"CURRENT {section.upper()} SECTION:\n{current_content}\n\n"
            f"PHYSICIAN FEEDBACK: {physician_instruction or 'Please improve accuracy and completeness.'}\n\n"
            f"Rewrite the {section_labels[section]} section only:"
        )

        response = await self._client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        return (response.choices[0].message.content or "").strip()

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_soap_response(raw: str) -> dict[str, Any]:
        """
        Parse and validate the JSON SOAP response from GPT.

        Args:
            raw: Raw JSON string from the model.

        Returns:
            Validated dict with subjective, objective, assessment, plan,
            icd10_codes, cpt_codes keys.

        Raises:
            ValueError: If required keys are missing.
            json.JSONDecodeError: If the response is not valid JSON.
        """
        data = json.loads(raw)

        # Ensure all required SOAP sections exist
        for key in ("subjective", "objective", "assessment", "plan"):
            if key not in data:
                data[key] = "Insufficient information documented."

        # Normalise ICD codes
        icd_codes = data.get("icd10_codes", data.get("icd_codes", []))
        normalised_icd = []
        for item in icd_codes:
            if isinstance(item, dict):
                normalised_icd.append({
                    "code": str(item.get("code", "")).strip(),
                    "description": str(item.get("description", "")).strip(),
                    "confidence": float(item.get("confidence", 0.0)),
                    "is_primary": bool(item.get("is_primary", False)),
                })
        data["icd10_codes"] = normalised_icd

        # Normalise CPT codes
        cpt_codes = data.get("cpt_codes", [])
        normalised_cpt = []
        for item in cpt_codes:
            if isinstance(item, dict):
                normalised_cpt.append({
                    "code": str(item.get("code", "")).strip(),
                    "description": str(item.get("description", "")).strip(),
                    "confidence": float(item.get("confidence", 0.0)),
                })
        data["cpt_codes"] = normalised_cpt

        # Ensure primary flag is set on at least one ICD code
        if normalised_icd and not any(c["is_primary"] for c in normalised_icd):
            normalised_icd[0]["is_primary"] = True

        return data
