"""Phase B + C tests for ClinNote — voice transcript ↔ SOAP clinical QA analyzer + brief PDF."""
from __future__ import annotations

import os

import pytest


pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _mock_fraud_gpt():
    os.environ["MOCK_FRAUD_GPT"] = "true"
    yield
    os.environ.pop("MOCK_FRAUD_GPT", None)


# ---- unit tests --------------------------------------------------------


async def test_voice_signals_meds_vitals_decision():
    from app.services.clinical_qa_analyzer import (
        detect_voice_signals, extract_voice_medications, extract_voice_allergies,
        extract_voice_vitals, extract_voice_icd_codes, extract_voice_cpt_codes,
        detect_missing_meds_in_plan, detect_missing_allergies_in_note,
        detect_missing_vitals_in_objective, detect_uncoded_icd, detect_uncoded_cpt,
        detect_critical_signal_not_escalated, detect_decision, ClinicalQAAnalyzer,
    )

    transcript = (
        "Patient presents with sore throat for three days. BP is 142/88, temperature 38.2 C, "
        "HR 96. Allergic to penicillin — important. Started ibuprofen 400 mg PO TID at home. "
        "On exam, throat erythematous. Suggest rapid strep test. Diagnosis is acute pharyngitis "
        "J02.9. Procedure 99213 for office visit. Patient also reports suicidal ideation in the "
        "last week — I will refer to psych and set up safety plan. I need to amend the note."
    )

    signals = detect_voice_signals(transcript)
    assert "critical_suicidal_ideation" in signals
    assert "decision_amend" in signals

    meds = extract_voice_medications(transcript)
    assert "ibuprofen" in meds

    allergies = extract_voice_allergies(transcript)
    assert any("penicillin" in a for a in allergies)

    vitals = extract_voice_vitals(transcript)
    assert vitals.get("bp_systolic") == 142
    assert vitals.get("bp_diastolic") == 88
    assert vitals.get("hr") == 96
    assert vitals.get("temp_value") == 38.2

    icds = extract_voice_icd_codes(transcript)
    assert "J02.9" in icds

    cpts = extract_voice_cpt_codes(transcript)
    assert "99213" in cpts

    # SOAP note with no ibuprofen / penicillin → both flagged
    missing_meds = detect_missing_meds_in_plan(
        meds,
        soap_plan="Rapid strep test. Acetaminophen 500 mg.",
        soap_subjective="Sore throat, 3 days.",
    )
    assert any(m["medication"] == "ibuprofen" for m in missing_meds)

    missing_allergies = detect_missing_allergies_in_note(
        allergies,
        soap_subjective="Sore throat, 3 days.",
        soap_assessment="Acute pharyngitis",
    )
    assert any("penicillin" in a["allergen"] for a in missing_allergies)

    missing_vitals = detect_missing_vitals_in_objective(
        vitals,
        soap_objective="Throat erythematous.",  # no BP, no temp, no HR
    )
    vital_names = {v["vital"] for v in missing_vitals}
    assert "blood_pressure" in vital_names

    # SOAP with no ICD coded — voice's J02.9 is uncoded
    uncoded_icd = detect_uncoded_icd(icds, soap_icd_codes=[])
    assert any(u["code"] == "J02.9" for u in uncoded_icd)

    # SOAP with no CPT — voice's 99213 is uncoded
    uncoded_cpt = detect_uncoded_cpt(cpts, soap_cpt_codes=[])
    assert any(u["code"] == "99213" for u in uncoded_cpt)

    # Suicidal ideation in voice, but plan only mentions strep + acetaminophen → unescalated
    critical_un = detect_critical_signal_not_escalated(
        signals,
        soap_plan="Rapid strep test. Acetaminophen 500 mg.",
        soap_assessment="Acute pharyngitis",
    )
    assert any(c["signal"] == "critical_suicidal_ideation" for c in critical_un)

    decision = detect_decision(signals)
    assert decision == "amend"

    analyzer = ClinicalQAAnalyzer()
    result = await analyzer.analyze(
        transcript,
        soap_note={
            "id": "n1",
            "subjective": "Sore throat, 3 days.",
            "objective": "Throat erythematous.",
            "assessment": "Acute pharyngitis",
            "plan": "Rapid strep test. Acetaminophen 500 mg.",
            "icd_codes": [],
            "cpt_codes": [],
        },
    )
    severities = {tp["severity"] for tp in result["talking_points"]}
    assert "critical" in severities
    assert result["decision"] == "amend"


async def test_clean_transcript_returns_summary():
    from app.services.clinical_qa_analyzer import ClinicalQAAnalyzer
    analyzer = ClinicalQAAnalyzer()
    result = await analyzer.analyze(
        "Follow-up visit. Patient stable. Continue current meds. I will sign the note.",
        soap_note={
            "subjective": "Follow-up.",
            "objective": "Stable.",
            "assessment": "Stable chronic condition.",
            "plan": "Continue meds.",
            "icd_codes": [],
            "cpt_codes": [],
        },
    )
    assert result["decision"] == "sign"
    topics = {tp["topic"] for tp in result["talking_points"]}
    assert "decision_sign" in topics


async def test_empty_returns_no_transcript():
    from app.services.clinical_qa_analyzer import ClinicalQAAnalyzer
    analyzer = ClinicalQAAnalyzer()
    result = await analyzer.analyze("", {})
    assert result["mode"] == "no_transcript"


async def test_critical_signal_escalated_in_plan_is_not_flagged():
    from app.services.clinical_qa_analyzer import detect_critical_signal_not_escalated

    signals = {"critical_suicidal_ideation": ["si positive"]}
    # Plan addresses the signal → not flagged
    out = detect_critical_signal_not_escalated(
        signals,
        soap_plan="Patient with suicidal ideation. Psychiatry consult ordered, safety plan in place.",
        soap_assessment="Major depression with suicidal ideation.",
    )
    assert out == []


async def test_pdf_renders_with_full_analyzer_output():
    from app.services.clinical_qa_analyzer import ClinicalQAAnalyzer
    from app.services.clinical_qa_brief_pdf_service import (
        render_clinical_qa_brief_pdf, safe_pdf_filename,
    )

    analyzer = ClinicalQAAnalyzer()
    result = await analyzer.analyze(
        "BP is 180/120, hypertensive crisis. Allergic to penicillin. Started lisinopril 10 mg. "
        "Diagnosis I10. I need to amend the note.",
        soap_note={
            "id": "n2",
            "specialty": "primary_care",
            "status": "draft",
            "subjective": "Headache.",
            "objective": "Patient appears anxious.",
            "assessment": "Hypertension.",
            "plan": "Recheck BP.",
            "icd_codes": [],
            "cpt_codes": [],
        },
    )

    pdf_bytes = render_clinical_qa_brief_pdf(
        soap_note={
            "id": "n2", "specialty": "primary_care", "status": "draft",
            "icd_codes": [], "cpt_codes": [],
        },
        transcript="BP is 180/120, hypertensive crisis...",
        voice_signals=result["voice_signals"],
        voice_medications=result["voice_medications"],
        voice_allergies=result["voice_allergies"],
        voice_vitals=result["voice_vitals"],
        voice_icd_codes=result["voice_icd_codes"],
        voice_cpt_codes=result["voice_cpt_codes"],
        missing_meds_in_plan=result["missing_meds_in_plan"],
        missing_allergies_in_note=result["missing_allergies_in_note"],
        missing_vitals_in_objective=result["missing_vitals_in_objective"],
        uncoded_icd=result["uncoded_icd"],
        uncoded_cpt=result["uncoded_cpt"],
        critical_unescalated=result["critical_unescalated"],
        decision=result["decision"],
        talking_points=result["talking_points"],
        generated_by="test@example.com",
    )
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 500
    fn = safe_pdf_filename("n2")
    assert fn.startswith("clinnote-brief-") and fn.endswith(".pdf")


async def test_safe_pdf_filename_strips_invalid_chars():
    from app.services.clinical_qa_brief_pdf_service import safe_pdf_filename
    assert safe_pdf_filename("abc/def\\ghi:jkl").startswith("clinnote-brief-abc-def-ghi-jkl")
