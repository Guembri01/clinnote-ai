"""Phase B — voice transcript ↔ SOAP note clinical QA cross-validation.

Per the PDF spec for project_03 (ClinNote AI):
    "Cross-references the ambient encounter transcript against the generated
     SOAP note + assigned ICD/CPT codes. Flags voice-only medications,
     allergies, or vitals that didn't land in the SOAP plan/objective,
     critical safety signals not escalated, and ICD/CPT coding misses.
     Surfaces a sign-vs-amend recommendation for the physician."
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional


_DOSE_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(?:mg|mcg|g|ml|units?|U/mL)\b",
    re.IGNORECASE,
)
_BP_RE = re.compile(r"\bBP\s*(?:is\s+)?(\d{2,3})/(\d{2,3})\b", re.IGNORECASE)
_TEMP_RE = re.compile(
    r"\b(?:temp(?:erature)?(?:\s+is)?\s+)?(\d{2,3}(?:\.\d)?)\s*°?\s*(C|F|Celsius|Fahrenheit)\b",
    re.IGNORECASE,
)
_HR_RE = re.compile(
    r"\b(?:HR|heart\s+rate|pulse)\s*(?:is\s+)?(\d{2,3})\b",
    re.IGNORECASE,
)
_SPO2_RE = re.compile(
    r"\b(?:SpO2|O2\s+sat|oxygen\s+saturation)\s*(?:is\s+)?(\d{2,3})\s*%?\b",
    re.IGNORECASE,
)
_ICD_RE = re.compile(r"\b([A-TV-Z]\d{2}(?:\.\d{1,4})?)\b")
_CPT_RE = re.compile(r"\b(\d{5})\b")

_MED_NAMES = [
    "acetaminophen", "tylenol", "ibuprofen", "advil", "motrin", "naproxen", "aspirin",
    "amoxicillin", "azithromycin", "ciprofloxacin", "cephalexin", "doxycycline",
    "metformin", "insulin", "glipizide", "lisinopril", "amlodipine", "metoprolol",
    "losartan", "hydrochlorothiazide", "atorvastatin", "simvastatin",
    "warfarin", "apixaban", "rivaroxaban", "clopidogrel", "heparin",
    "albuterol", "fluticasone", "montelukast", "prednisone", "prednisolone",
    "ondansetron", "promethazine", "metoclopramide",
    "omeprazole", "pantoprazole", "famotidine",
    "sertraline", "fluoxetine", "escitalopram", "trazodone", "alprazolam",
    "morphine", "oxycodone", "hydrocodone", "fentanyl", "tramadol",
    "epinephrine", "diphenhydramine", "benadryl",
]
_MED_RE = re.compile(r"\b(" + "|".join(_MED_NAMES) + r")\b", re.IGNORECASE)

_ALLERGY_PATTERNS = [
    r"\b(?:allergic\s+to|allergy\s+to|allergies?\s+(?:include|are))\s+([a-zA-Z][\w\s,-]{2,40})\b",
    r"\b([A-Za-z]+)\s+allergy\b",
    r"\bNKA\b", r"\bNKDA\b",
]

_RISK_PATTERNS: Dict[str, List[str]] = {
    "critical_suicidal_ideation": [
        r"\bsuicid(?:al|e)\s+ideation\b",
        r"\bwants\s+to\s+(?:kill\s+himself|kill\s+herself|end\s+(?:his|her)\s+life)\b",
        r"\bsi\b\s+(?:positive|present)\b",
    ],
    "critical_anaphylaxis": [
        r"\banaphyla(?:xis|ctic)\b",
        r"\bairway\s+swelling\b",
        r"\bangioedema\b",
    ],
    "critical_sepsis_criteria": [
        r"\bseptic\b", r"\bsepsis\b",
        r"\bSIRS\b",
        r"\blactate\s+>?\s*(?:2|4)\b",
    ],
    "critical_severe_bleeding": [
        r"\bsevere\s+bleeding\b", r"\bhemorrhag(?:e|ic)\b",
        r"\bGI\s+bleed\b",
    ],
    "critical_hypertensive_crisis": [
        r"\bhypertensive\s+(?:crisis|emergency|urgency)\b",
    ],
    "critical_dka": [
        r"\bDKA\b", r"\bdiabetic\s+keto[-\s]?acidosis\b",
    ],
    "critical_stroke_symptoms": [
        r"\bstroke\s+symptoms\b", r"\bfacial\s+droop\b",
        r"\bone[-\s]sided\s+weakness\b",
    ],
    "code_status_change": [
        r"\bDNR\b", r"\bdo\s+not\s+resuscitate\b",
        r"\bcode\s+status\b", r"\bDNI\b",
    ],
    "decision_sign": [
        r"\b(?:i\s+)?(?:will\s+)?sign\s+(?:this|the)\s+note\b",
        r"\bready\s+to\s+sign\b",
        r"\bnote\s+is\s+complete\b",
    ],
    "decision_amend": [
        r"\b(?:needs?|require[s]?)\s+(?:amend(?:ment)?|edits?|correction)\b",
        r"\b(?:i\s+)?need\s+to\s+(?:add|amend|edit)\b",
    ],
    "decision_hold": [
        r"\b(?:hold|pause)\s+(?:the\s+)?note\b",
        r"\bdon'?t\s+sign\s+yet\b",
        r"\bneed[s]?\s+more\s+(?:info|information|labs|imaging)\b",
    ],
    "decision_regenerate": [
        r"\bregenerate\s+(?:the\s+)?(?:note|soap)\b",
        r"\bre[-\s]?run\s+(?:the\s+)?soap\b",
    ],
}


def _find(text: str, patterns: List[str]) -> List[str]:
    if not text:
        return []
    out: list[str] = []
    for pat in patterns:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            start = max(0, m.start() - 20)
            end = min(len(text), m.end() + 50)
            span = text[start:end].strip()
            if span and span not in out:
                out.append(span)
    return out[:3]


def detect_voice_signals(transcript: str) -> Dict[str, List[str]]:
    return {k: ev for k, p in _RISK_PATTERNS.items() if (ev := _find(transcript, p))}


def extract_voice_medications(transcript: str) -> List[str]:
    if not transcript:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in _MED_RE.finditer(transcript):
        name = m.group(1).lower()
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def extract_voice_doses(transcript: str) -> List[str]:
    if not transcript:
        return []
    return [m.group(0).strip() for m in _DOSE_RE.finditer(transcript)][:10]


def extract_voice_allergies(transcript: str) -> List[str]:
    if not transcript:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for pat in _ALLERGY_PATTERNS:
        for m in re.finditer(pat, transcript, flags=re.IGNORECASE):
            raw = m.group(0).strip()
            # Trim to a single allergen guess
            text = m.group(1) if m.lastindex and m.lastindex >= 1 else raw
            text = (text or "").strip().lower().rstrip(".,;:")
            text = re.sub(r"\s+", " ", text)
            if text and text not in seen and len(text) < 60:
                seen.add(text)
                out.append(text)
    return out[:5]


def extract_voice_vitals(transcript: str) -> Dict[str, Any]:
    if not transcript:
        return {}
    out: Dict[str, Any] = {}
    bp = _BP_RE.search(transcript)
    if bp:
        out["bp_systolic"] = int(bp.group(1))
        out["bp_diastolic"] = int(bp.group(2))
    temp = _TEMP_RE.search(transcript)
    if temp:
        out["temp_value"] = float(temp.group(1))
        out["temp_unit"] = (temp.group(2) or "C").upper()[0]
    hr = _HR_RE.search(transcript)
    if hr:
        out["hr"] = int(hr.group(1))
    spo2 = _SPO2_RE.search(transcript)
    if spo2:
        out["spo2"] = int(spo2.group(1))
    return out


def extract_voice_icd_codes(transcript: str) -> List[str]:
    if not transcript:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in _ICD_RE.finditer(transcript):
        code = m.group(1).upper()
        if code not in seen:
            seen.add(code)
            out.append(code)
    return out


def extract_voice_cpt_codes(transcript: str) -> List[str]:
    if not transcript:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in _CPT_RE.finditer(transcript):
        code = m.group(1)
        if code not in seen:
            seen.add(code)
            out.append(code)
    return out


def detect_missing_meds_in_plan(
    voice_meds: List[str],
    soap_plan: str,
    soap_subjective: str,
) -> List[Dict[str, Any]]:
    out: list[dict] = []
    plan_lower = (soap_plan or "").lower()
    subj_lower = (soap_subjective or "").lower()
    for med in voice_meds:
        if med not in plan_lower and med not in subj_lower:
            out.append({
                "medication": med,
                "severity": "medium",
                "note": (
                    f"Voice mentions '{med}' but the SOAP plan/subjective doesn't reference it. "
                    "Confirm if it was discussed but not prescribed, or add it to plan."
                ),
            })
    return out[:5]


def detect_missing_allergies_in_note(
    voice_allergies: List[str],
    soap_subjective: str,
    soap_assessment: str,
) -> List[Dict[str, Any]]:
    if not voice_allergies:
        return []
    subj = (soap_subjective or "").lower()
    asse = (soap_assessment or "").lower()
    out: list[dict] = []
    for a in voice_allergies:
        if a in {"nka", "nkda"}:
            continue
        if a not in subj and a not in asse:
            out.append({
                "allergen": a,
                "severity": "high",
                "note": (
                    f"Voice mentions allergy '{a}' but it isn't on the SOAP "
                    "subjective/assessment. Add to allergy list before signing."
                ),
            })
    return out[:5]


def detect_missing_vitals_in_objective(
    voice_vitals: Dict[str, Any],
    soap_objective: str,
) -> List[Dict[str, Any]]:
    if not voice_vitals:
        return []
    obj_lower = (soap_objective or "").lower()
    out: list[dict] = []
    if "bp_systolic" in voice_vitals:
        bp_str = f"{voice_vitals['bp_systolic']}/{voice_vitals['bp_diastolic']}"
        if bp_str not in obj_lower and "bp" not in obj_lower:
            out.append({
                "vital": "blood_pressure",
                "voice_value": bp_str,
                "severity": "medium",
                "note": f"Voice cites BP {bp_str} but SOAP objective doesn't include it.",
            })
    if "temp_value" in voice_vitals:
        if "temp" not in obj_lower and "fever" not in obj_lower:
            out.append({
                "vital": "temperature",
                "voice_value": f"{voice_vitals['temp_value']}°{voice_vitals.get('temp_unit','C')}",
                "severity": "low",
                "note": "Voice cites temperature but SOAP objective doesn't include it.",
            })
    if "hr" in voice_vitals and "hr" not in obj_lower and "heart rate" not in obj_lower and "pulse" not in obj_lower:
        out.append({
            "vital": "heart_rate",
            "voice_value": str(voice_vitals["hr"]),
            "severity": "low",
            "note": "Voice cites heart rate but SOAP objective doesn't include it.",
        })
    return out


def detect_uncoded_icd(
    voice_icds: List[str],
    soap_icd_codes: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    coded = {(c.get("code") or "").upper() for c in (soap_icd_codes or [])}
    out: list[dict] = []
    for code in voice_icds:
        if code not in coded:
            out.append({
                "code": code,
                "severity": "medium",
                "note": (
                    f"Voice references ICD-10-CM {code} but it isn't on the SOAP note's "
                    "icd_codes list. Add the code + confirm primary/secondary."
                ),
            })
    return out[:5]


def detect_uncoded_cpt(
    voice_cpts: List[str],
    soap_cpt_codes: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    coded = {(c.get("code") or "") for c in (soap_cpt_codes or [])}
    out: list[dict] = []
    for code in voice_cpts:
        if code not in coded:
            out.append({
                "code": code,
                "severity": "low",
                "note": (
                    f"Voice mentions {code} (potential CPT) but it isn't on the SOAP "
                    "cpt_codes list. Confirm if procedure was billable."
                ),
            })
    return out[:5]


def detect_critical_signal_not_escalated(
    voice_signals: Dict[str, List[str]],
    soap_plan: str,
    soap_assessment: str,
) -> List[Dict[str, Any]]:
    plan_lower = (soap_plan or "").lower()
    asse_lower = (soap_assessment or "").lower()
    out: list[dict] = []
    critical_keys = [k for k in voice_signals if k.startswith("critical_")]
    for key in critical_keys:
        topic = key.replace("critical_", "")
        echo_terms = topic.replace("_", " ").split()
        echoed = any(term in plan_lower or term in asse_lower for term in echo_terms if len(term) > 3)
        if not echoed:
            out.append({
                "signal": key,
                "evidence": voice_signals[key][:2],
                "severity": "critical",
                "note": (
                    f"Voice flagged {key.replace('_',' ')} but the SOAP assessment/plan "
                    "doesn't address it. ADD URGENT action before signing."
                ),
            })
    return out[:5]


def detect_decision(signals: Dict[str, List[str]]) -> str:
    if "decision_hold" in signals:
        return "hold"
    if "decision_regenerate" in signals:
        return "regenerate"
    if "decision_amend" in signals:
        return "amend"
    if "decision_sign" in signals:
        return "sign"
    return "unspecified"


class ClinicalQAAnalyzer:
    def __init__(self) -> None:
        self.mock_mode = (
            os.environ.get("MOCK_FRAUD_GPT", "").lower() in {"1", "true", "yes"}
            or not os.environ.get("OPENAI_API_KEY")
        )

    async def analyze(
        self,
        transcript: str,
        soap_note: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not (transcript or "").strip():
            return {
                "mode": "no_transcript",
                "voice_signals": {},
                "voice_medications": [],
                "voice_doses": [],
                "voice_allergies": [],
                "voice_vitals": {},
                "voice_icd_codes": [],
                "voice_cpt_codes": [],
                "missing_meds_in_plan": [],
                "missing_allergies_in_note": [],
                "missing_vitals_in_objective": [],
                "uncoded_icd": [],
                "uncoded_cpt": [],
                "critical_unescalated": [],
                "decision": "unspecified",
                "talking_points": [],
            }

        signals = detect_voice_signals(transcript)
        meds = extract_voice_medications(transcript)
        doses = extract_voice_doses(transcript)
        allergies = extract_voice_allergies(transcript)
        vitals = extract_voice_vitals(transcript)
        v_icds = extract_voice_icd_codes(transcript)
        v_cpts = extract_voice_cpt_codes(transcript)

        plan = soap_note.get("plan") or ""
        subjective = soap_note.get("subjective") or ""
        objective = soap_note.get("objective") or ""
        assessment = soap_note.get("assessment") or ""

        missing_meds = detect_missing_meds_in_plan(meds, plan, subjective)
        missing_allergies = detect_missing_allergies_in_note(allergies, subjective, assessment)
        missing_vitals = detect_missing_vitals_in_objective(vitals, objective)
        uncoded_icd = detect_uncoded_icd(v_icds, soap_note.get("icd_codes") or [])
        uncoded_cpt = detect_uncoded_cpt(v_cpts, soap_note.get("cpt_codes") or [])
        critical_un = detect_critical_signal_not_escalated(signals, plan, assessment)
        decision = detect_decision(signals)

        talking_points: list[dict] = []
        for c in critical_un:
            talking_points.append({
                "topic": c["signal"],
                "severity": "critical",
                "point": c["note"],
            })
        if "code_status_change" in signals:
            talking_points.append({
                "topic": "code_status_change",
                "severity": "high",
                "point": (
                    "Voice flagged code-status change (DNR/DNI) — verify documentation "
                    "in advance directive + confirm with patient/family before signing."
                ),
            })
        for a in missing_allergies:
            talking_points.append({
                "topic": "missing_allergy",
                "severity": "high",
                "point": a["note"],
            })
        for m in missing_meds:
            talking_points.append({
                "topic": "missing_medication",
                "severity": "medium",
                "point": m["note"],
            })
        for v in missing_vitals:
            talking_points.append({
                "topic": "missing_vital",
                "severity": v.get("severity", "low"),
                "point": v["note"],
            })
        for u in uncoded_icd:
            talking_points.append({
                "topic": "uncoded_icd",
                "severity": "medium",
                "point": u["note"],
            })
        for c in uncoded_cpt:
            talking_points.append({
                "topic": "uncoded_cpt",
                "severity": "low",
                "point": c["note"],
            })
        if decision == "hold":
            talking_points.append({
                "topic": "decision_hold",
                "severity": "medium",
                "point": "Physician decision: HOLD — collect more info before signing.",
            })
        elif decision == "regenerate":
            talking_points.append({
                "topic": "decision_regenerate",
                "severity": "medium",
                "point": "Physician decision: REGENERATE — re-run SOAP service on corrected transcript.",
            })
        elif decision == "amend":
            talking_points.append({
                "topic": "decision_amend",
                "severity": "medium",
                "point": "Physician decision: AMEND — apply edits before signing.",
            })
        elif decision == "sign":
            talking_points.append({
                "topic": "decision_sign",
                "severity": "info",
                "point": "Physician decision: SIGN — clear to approve once flags addressed.",
            })
        if not talking_points:
            talking_points.append({
                "topic": "summary",
                "severity": "info",
                "point": "Voice transcript consistent with SOAP note + codes.",
            })

        return {
            "mode": "deterministic",
            "voice_signals": signals,
            "voice_medications": meds,
            "voice_doses": doses,
            "voice_allergies": allergies,
            "voice_vitals": vitals,
            "voice_icd_codes": v_icds,
            "voice_cpt_codes": v_cpts,
            "missing_meds_in_plan": missing_meds,
            "missing_allergies_in_note": missing_allergies,
            "missing_vitals_in_objective": missing_vitals,
            "uncoded_icd": uncoded_icd,
            "uncoded_cpt": uncoded_cpt,
            "critical_unescalated": critical_un,
            "decision": decision,
            "talking_points": talking_points,
        }
