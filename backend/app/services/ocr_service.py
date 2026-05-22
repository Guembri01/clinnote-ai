from __future__ import annotations
"""
ClinNote AI — Azure Document Intelligence OCR Service
=======================================================
Extracts structured data from lab reports, intake forms, and other
clinical documents using Azure Document Intelligence (formerly Form Recognizer).

Models used:
  - prebuilt-document : General document extraction (lab reports)
  - prebuilt-layout   : Form field extraction (intake forms)

API:
  POST {endpoint}/documentintelligence/documentModels/{modelId}:analyze
  Ocp-Apim-Subscription-Key: {key}

HIPAA Note:
  Documents are sent to Azure under a BAA. No raw document bytes are
  stored by this application — only the extracted structured data.
"""


import asyncio
import logging
from typing import Any

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Common lab result patterns to extract
LAB_FIELD_KEYWORDS = {
    "glucose", "sodium", "potassium", "chloride", "co2", "bun", "creatinine",
    "gfr", "calcium", "albumin", "protein", "bilirubin", "ast", "alt", "alk phos",
    "wbc", "rbc", "hemoglobin", "hematocrit", "platelets", "mcv", "mchc",
    "hba1c", "tsh", "t4", "psa", "ldl", "hdl", "triglycerides", "cholesterol",
    "bnp", "troponin", "inr", "pt", "aptt", "crp", "esr",
}


class OCRService:
    """
    Azure Document Intelligence client for clinical document OCR.

    Usage:
        svc = OCRService()
        lab_data = await svc.extract_lab_report(file_bytes, "lab_result.pdf")
    """

    def __init__(self) -> None:
        self._client = DocumentIntelligenceClient(
            endpoint=settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT,
            credential=AzureKeyCredential(settings.AZURE_DOCUMENT_INTELLIGENCE_KEY),
        )

    async def extract_lab_report(
        self,
        file_bytes: bytes,
        file_name: str,
    ) -> dict[str, Any]:
        """
        Extract lab values, reference ranges, and abnormal flags from a lab report.

        Args:
            file_bytes: Raw PDF or image bytes of the lab report.
            file_name : Original filename (used for MIME type detection).

        Returns:
            dict with keys:
              - lab_values  : [{name, value, unit, reference_range, flag, confidence}]
              - raw_text    : Full extracted text from the document.
              - page_count  : Number of pages processed.
              - model_used  : Azure model ID used.
              - confidence  : Overall extraction confidence.

        Raises:
            HttpResponseError: On Azure API error.
            RuntimeError: If extraction fails after retries.
        """
        logger.info("Extracting lab report: %s (%d bytes)", file_name, len(file_bytes))

        result = await self._analyze_document(
            file_bytes=file_bytes,
            model_id="prebuilt-document",
        )

        lab_values = self._extract_lab_values(result)
        raw_text = self._extract_raw_text(result)

        return {
            "lab_values": lab_values,
            "raw_text": raw_text,
            "page_count": len(result.pages) if hasattr(result, "pages") and result.pages else 0,
            "model_used": "prebuilt-document",
            "confidence": self._calculate_confidence(result),
        }

    async def process_intake_form(
        self,
        file_bytes: bytes,
    ) -> dict[str, Any]:
        """
        Extract vitals, medications, and allergies from a patient intake form.

        Args:
            file_bytes: Raw PDF or image bytes of the intake form.

        Returns:
            dict with keys:
              - vitals      : {bp, hr, temp, rr, spo2, weight, height}
              - medications : [str] — list of current medications
              - allergies   : [str] — list of known allergies
              - chief_complaint: str
              - raw_fields  : {field_name: {value, confidence}} — all extracted fields
              - raw_text    : Full extracted text.

        Raises:
            HttpResponseError: On Azure API error.
        """
        logger.info("Processing intake form (%d bytes)", len(file_bytes))

        result = await self._analyze_document(
            file_bytes=file_bytes,
            model_id="prebuilt-layout",
        )

        raw_text = self._extract_raw_text(result)
        raw_fields = self._extract_key_value_pairs(result)

        return {
            "vitals": self._extract_vitals(raw_fields, raw_text),
            "medications": self._extract_list_field(raw_fields, raw_text, "medication"),
            "allergies": self._extract_list_field(raw_fields, raw_text, "allerg"),
            "chief_complaint": self._find_field(raw_fields, "chief complaint") or
                               self._find_field(raw_fields, "reason for visit"),
            "raw_fields": raw_fields,
            "raw_text": raw_text,
        }

    async def extract_document_text(self, file_bytes: bytes) -> str:
        """
        Simple full-text extraction from any document.

        Args:
            file_bytes: Raw document bytes.

        Returns:
            Extracted plain text string.
        """
        result = await self._analyze_document(file_bytes, "prebuilt-document")
        return self._extract_raw_text(result)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    async def _analyze_document(
        self,
        file_bytes: bytes,
        model_id: str,
        max_retries: int = 3,
    ) -> Any:
        """
        Submit a document for analysis and poll until complete.

        Args:
            file_bytes: Raw document bytes.
            model_id  : Azure Document Intelligence model ID.
            max_retries: Number of retry attempts on transient errors.

        Returns:
            AnalyzeResult from Azure SDK.

        Raises:
            RuntimeError: After max_retries exhausted.
        """
        last_exc: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                # Azure SDK is synchronous; run in thread pool for async compatibility
                loop = asyncio.get_event_loop()
                poller = await loop.run_in_executor(
                    None,
                    lambda: self._client.begin_analyze_document(
                        model_id,
                        AnalyzeDocumentRequest(bytes_source=file_bytes),
                    ),
                )
                result = await loop.run_in_executor(None, poller.result)
                return result

            except HttpResponseError as exc:
                logger.warning(
                    "Azure DI API error attempt %d/%d: %s", attempt, max_retries, exc
                )
                last_exc = exc
                if exc.status_code in (400, 401, 403):
                    raise
                if attempt < max_retries:
                    await asyncio.sleep(2.0 ** attempt)

        raise RuntimeError(
            f"Azure Document Intelligence failed after {max_retries} attempts: {last_exc}"
        )

    @staticmethod
    def _extract_raw_text(result: Any) -> str:
        """Extract all text content from the analysis result."""
        if not hasattr(result, "content"):
            return ""
        return result.content or ""

    @staticmethod
    def _extract_key_value_pairs(result: Any) -> dict[str, dict]:
        """Extract key-value pairs from the document."""
        pairs: dict[str, dict] = {}
        if not hasattr(result, "key_value_pairs") or not result.key_value_pairs:
            return pairs

        for kv in result.key_value_pairs:
            if kv.key and kv.key.content:
                key = kv.key.content.strip().lower()
                value = ""
                confidence = 0.0
                if kv.value and kv.value.content:
                    value = kv.value.content.strip()
                if hasattr(kv, "confidence"):
                    confidence = kv.confidence or 0.0
                pairs[key] = {"value": value, "confidence": confidence}

        return pairs

    def _extract_lab_values(self, result: Any) -> list[dict[str, Any]]:
        """
        Parse lab values from extracted key-value pairs and raw text.
        Looks for patterns like: "Glucose  95  mg/dL  70-100  Normal"
        """
        lab_values = []
        raw_fields = self._extract_key_value_pairs(result)

        for field_name, field_data in raw_fields.items():
            # Check if this field looks like a lab result
            if any(keyword in field_name.lower() for keyword in LAB_FIELD_KEYWORDS):
                value_str = field_data.get("value", "")
                parsed = self._parse_lab_value_string(value_str)
                lab_values.append({
                    "name": field_name.title(),
                    "value": parsed.get("value"),
                    "unit": parsed.get("unit"),
                    "reference_range": parsed.get("reference_range"),
                    "flag": parsed.get("flag"),
                    "confidence": field_data.get("confidence", 0.0),
                })

        return lab_values

    @staticmethod
    def _parse_lab_value_string(value_str: str) -> dict[str, str | None]:
        """
        Parse a lab value string like "95 mg/dL (70-100) H" into components.

        Returns dict: {value, unit, reference_range, flag}
        """
        import re
        result = {"value": None, "unit": None, "reference_range": None, "flag": None}

        if not value_str:
            return result

        # Flag (H/L/HH/LL/*)
        flag_match = re.search(r"\b(HH|LL|H|L|\*)\b", value_str)
        if flag_match:
            result["flag"] = flag_match.group(1)
            value_str = value_str[:flag_match.start()].strip()

        # Reference range in parentheses: (70-100)
        range_match = re.search(r"\(([^)]+)\)", value_str)
        if range_match:
            result["reference_range"] = range_match.group(1)
            value_str = value_str.replace(range_match.group(0), "").strip()

        # Unit — common medical units
        unit_match = re.search(
            r"\b(mg/dL|mmol/L|mEq/L|g/dL|U/L|IU/L|%|K/µL|M/µL|pg|fL|ng/mL|µg/dL|"
            r"mIU/mL|pmol/L|nmol/L|mmHg|bpm)\b",
            value_str,
        )
        if unit_match:
            result["unit"] = unit_match.group(1)
            value_str = value_str.replace(unit_match.group(0), "").strip()

        # Numeric value
        num_match = re.search(r"[\d.]+", value_str)
        if num_match:
            result["value"] = num_match.group(0)

        return result

    @staticmethod
    def _extract_vitals(fields: dict, raw_text: str) -> dict[str, str | None]:
        """Extract common vital sign fields."""
        import re

        def find(keywords: list[str]) -> str | None:
            for kw in keywords:
                for field_name, data in fields.items():
                    if kw in field_name:
                        return data.get("value")
            return None

        vitals: dict[str, str | None] = {
            "bp": find(["blood pressure", "bp", "b/p"]),
            "hr": find(["heart rate", "hr", "pulse"]),
            "temp": find(["temperature", "temp"]),
            "rr": find(["respiratory", "rr", "resp rate"]),
            "spo2": find(["oxygen", "spo2", "o2 sat", "sat"]),
            "weight": find(["weight", "wt"]),
            "height": find(["height", "ht"]),
        }

        # Fall back to raw text regex
        if not vitals["bp"]:
            m = re.search(r"BP[:\s]*(\d{2,3}/\d{2,3})", raw_text, re.IGNORECASE)
            if m:
                vitals["bp"] = m.group(1)

        if not vitals["hr"]:
            m = re.search(r"HR[:\s]*(\d{2,3})", raw_text, re.IGNORECASE)
            if m:
                vitals["hr"] = m.group(1)

        return vitals

    @staticmethod
    def _extract_list_field(fields: dict, raw_text: str, keyword: str) -> list[str]:
        """Extract a list of items for fields like medications/allergies."""
        for field_name, data in fields.items():
            if keyword in field_name.lower():
                value = data.get("value", "")
                if value:
                    # Split by common delimiters
                    import re
                    items = re.split(r"[,;\n•]", value)
                    return [item.strip() for item in items if item.strip()]
        return []

    @staticmethod
    def _find_field(fields: dict, keyword: str) -> str | None:
        """Find a field value by keyword match."""
        for field_name, data in fields.items():
            if keyword in field_name.lower():
                return data.get("value")
        return None

    @staticmethod
    def _calculate_confidence(result: Any) -> float:
        """Calculate overall extraction confidence from the result."""
        if not hasattr(result, "key_value_pairs") or not result.key_value_pairs:
            return 0.0
        confidences = [
            kv.confidence
            for kv in result.key_value_pairs
            if hasattr(kv, "confidence") and kv.confidence is not None
        ]
        if not confidences:
            return 0.0
        return round(sum(confidences) / len(confidences), 4)
