from __future__ import annotations
"""
ClinNote AI — Medical Vocabulary Correction Dictionary
=========================================================
Common Whisper transcription errors for medical terminology.
Applied as a post-processing step after Whisper output to improve
accuracy before SOAP note generation.

Categories:
  - Medications (brand and generic names)
  - Anatomical terms
  - Procedure abbreviations
  - Lab values and units
  - Diagnoses / disease names
  - Medical abbreviations
"""


import re
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Correction map: (pattern, replacement)
# Patterns are case-insensitive regex; replacements preserve original case style
# ---------------------------------------------------------------------------
MEDICAL_CORRECTIONS: List[Tuple[str, str]] = [
    # Medications — common Whisper mishearings
    (r"\bmetformin\b", "metformin"),
    (r"\bamlodopine\b", "amlodipine"),
    (r"\blisnopril\b", "lisinopril"),
    (r"\blisonopril\b", "lisinopril"),
    (r"\batorvastatin\b", "atorvastatin"),
    (r"\battorvastatin\b", "atorvastatin"),
    (r"\blevothyroxine\b", "levothyroxine"),
    (r"\blevothirozine\b", "levothyroxine"),
    (r"\bomeprazol\b", "omeprazole"),
    (r"\bomeprazal\b", "omeprazole"),
    (r"\bsertraline\b", "sertraline"),
    (r"\bsertarline\b", "sertraline"),
    (r"\bhydrochlorothiazide\b", "hydrochlorothiazide"),
    (r"\bhctz\b", "HCTZ"),
    (r"\bwarferin\b", "warfarin"),
    (r"\bwarfarin\b", "warfarin"),
    (r"\bclopidogrel\b", "clopidogrel"),
    (r"\bplavix\b", "Plavix"),
    (r"\blasix\b", "Lasix"),
    (r"\bfurosemide\b", "furosemide"),
    (r"\bprednisone\b", "prednisone"),
    (r"\bprednizone\b", "prednisone"),
    (r"\baspirin\b", "aspirin"),
    (r"\bmetoporol\b", "metoprolol"),
    (r"\bmetoprolal\b", "metoprolol"),
    (r"\bmetoprolol\b", "metoprolol"),
    (r"\bgabapentin\b", "gabapentin"),
    (r"\bgabapentine\b", "gabapentin"),
    (r"\bamoxacillin\b", "amoxicillin"),
    (r"\bamoxicillan\b", "amoxicillin"),
    (r"\bazithromycin\b", "azithromycin"),
    (r"\bazythromycin\b", "azithromycin"),
    (r"\bciprofloxicin\b", "ciprofloxacin"),
    (r"\bciprofloxacin\b", "ciprofloxacin"),
    (r"\bibuprofen\b", "ibuprofen"),
    (r"\bacetaminophen\b", "acetaminophen"),
    (r"\btylenol\b", "Tylenol"),
    (r"\balbuterol\b", "albuterol"),
    (r"\bventolin\b", "Ventolin"),
    (r"\binsulin\b", "insulin"),
    (r"\bglucophage\b", "Glucophage"),
    (r"\bxarelto\b", "Xarelto"),
    (r"\brivaroxaban\b", "rivaroxaban"),
    (r"\beliquis\b", "Eliquis"),
    (r"\bapixaban\b", "apixaban"),

    # Diagnoses
    (r"\bhyperglycemia\b", "hyperglycemia"),
    (r"\bhypoglycemia\b", "hypoglycemia"),
    (r"\bhypertension\b", "hypertension"),
    (r"\bhypotension\b", "hypotension"),
    (r"\bdiabetes mellitis\b", "diabetes mellitus"),
    (r"\bdiabetes mellatis\b", "diabetes mellitus"),
    (r"\bmyocardial infraction\b", "myocardial infarction"),
    (r"\bmyocardial infarktion\b", "myocardial infarction"),
    (r"\bcongestive heart failure\b", "congestive heart failure"),
    (r"\bchf\b", "CHF"),
    (r"\bcopd\b", "COPD"),
    (r"\bchronic obstructive pulmonary disease\b", "chronic obstructive pulmonary disease"),
    (r"\buti\b", "UTI"),
    (r"\burinary tract infection\b", "urinary tract infection"),
    (r"\bpneumonia\b", "pneumonia"),
    (r"\bpnuemonia\b", "pneumonia"),
    (r"\bcelulitis\b", "cellulitis"),
    (r"\bcellulitis\b", "cellulitis"),
    (r"\bappendisitis\b", "appendicitis"),
    (r"\bappendicitis\b", "appendicitis"),
    (r"\bdepression\b", "depression"),
    (r"\banxiety\b", "anxiety"),

    # Anatomical terms
    (r"\bdysphasia\b", "dysphagia"),
    (r"\bdysphagia\b", "dysphagia"),
    (r"\bdyspnea\b", "dyspnea"),
    (r"\bdispnea\b", "dyspnea"),
    (r"\borthopnea\b", "orthopnea"),
    (r"\btachycardia\b", "tachycardia"),
    (r"\btachycardea\b", "tachycardia"),
    (r"\bbradycardia\b", "bradycardia"),
    (r"\bpalpitations\b", "palpitations"),
    (r"\bpalpetations\b", "palpitations"),
    (r"\bnausea\b", "nausea"),
    (r"\bnauzia\b", "nausea"),
    (r"\bdiarrhea\b", "diarrhea"),
    (r"\bdiarrea\b", "diarrhea"),
    (r"\bconstipation\b", "constipation"),
    (r"\bedema\b", "edema"),
    (r"\boeadema\b", "edema"),
    (r"\bsyncope\b", "syncope"),
    (r"\bsynkope\b", "syncope"),

    # Labs & units
    (r"\bmilligrams per deciliter\b", "mg/dL"),
    (r"\bmg per dl\b", "mg/dL"),
    (r"\bmillimoles per liter\b", "mmol/L"),
    (r"\binternational units\b", "IU"),
    (r"\bbun\b", "BUN"),
    (r"\bgfr\b", "GFR"),
    (r"\bhmb a1c\b", "HbA1c"),
    (r"\bhemoglobin a1 c\b", "HbA1c"),
    (r"\bhemoglobin a one c\b", "HbA1c"),
    (r"\bcbc\b", "CBC"),
    (r"\bcmp\b", "CMP"),
    (r"\bbnp\b", "BNP"),
    (r"\bekg\b", "EKG"),
    (r"\becg\b", "ECG"),

    # Procedures
    (r"\bechocardiogram\b", "echocardiogram"),
    (r"\bechocardiagram\b", "echocardiogram"),
    (r"\bendoscopy\b", "endoscopy"),
    (r"\bcolonoscopy\b", "colonoscopy"),
    (r"\bcolonoscapy\b", "colonoscopy"),
    (r"\bcatheterization\b", "catheterization"),
    (r"\bpercutaneous coronary intervention\b", "percutaneous coronary intervention"),
    (r"\bpci\b", "PCI"),
    (r"\bcabg\b", "CABG"),
    (r"\bcoronary artery bypass graft\b", "coronary artery bypass graft"),

    # Common abbreviations
    (r"\bbid\b", "BID"),
    (r"\btid\b", "TID"),
    (r"\bqid\b", "QID"),
    (r"\bprn\b", "PRN"),
    (r"\bqd\b", "QD"),
    (r"\bpo\b", "PO"),
    (r"\biv\b", "IV"),
    (r"\bim\b", "IM"),
    (r"\bsc\b", "SC"),
    (r"\bnpo\b", "NPO"),
    (r"\bstat\b", "STAT"),
    (r"\bhpi\b", "HPI"),
    (r"\bros\b", "ROS"),
    (r"\bpe\b", "PE"),
    (r"\bvs\b", "VS"),
    (r"\bwbc\b", "WBC"),
    (r"\brbc\b", "RBC"),
    (r"\bhgb\b", "Hgb"),
    (r"\bhct\b", "Hct"),
    (r"\bplts\b", "Plts"),
    (r"\bna\b(?= )", "Na"),
    (r"\bk\b(?= )", "K"),
    (r"\bcl\b(?= )", "Cl"),
    (r"\bco2\b", "CO2"),
    (r"\bcr\b(?= )", "Cr"),
    (r"\balt\b(?= )", "ALT"),
    (r"\bast\b(?= )", "AST"),
]

# Compiled pattern cache
_COMPILED_PATTERNS: List[Tuple[re.Pattern, str]] | None = None


def _get_compiled_patterns() -> List[Tuple[re.Pattern, str]]:
    """Lazily compile and cache all correction patterns."""
    global _COMPILED_PATTERNS
    if _COMPILED_PATTERNS is None:
        _COMPILED_PATTERNS = [
            (re.compile(pattern, re.IGNORECASE), replacement)
            for pattern, replacement in MEDICAL_CORRECTIONS
        ]
    return _COMPILED_PATTERNS


def apply_medical_corrections(text: str) -> str:
    """
    Apply all medical vocabulary corrections to a transcription string.

    Args:
        text: Raw Whisper transcription output.

    Returns:
        Corrected text with proper medical terminology.

    Notes:
        - Replacements are applied in order; earlier rules take precedence.
        - Case-insensitive matching; replacement preserves the given casing.
        - Safe to call on empty or None input.
    """
    if not text:
        return text or ""

    for pattern, replacement in _get_compiled_patterns():
        text = pattern.sub(replacement, text)

    return text


def get_all_medical_terms() -> List[str]:
    """Return a flat list of all canonical medical terms in the dictionary."""
    return [replacement for _, replacement in MEDICAL_CORRECTIONS]
