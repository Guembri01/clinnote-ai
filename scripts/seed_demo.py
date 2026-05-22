#!/usr/bin/env python3
"""
ClinNote AI — Demo Data Seed Script (INVESTOR-GRADE)
=====================================================
Bootstraps an end-to-end demo dataset that makes the AI output *visible*:

  1. Admin (Alexandra Chen)
  2. 6 physicians (diverse specialties) + 1 nurse
  3. 20 patients (diverse demographics, ages 24–82)
  4. 18 recording sessions staggered over last 30 days
  5. Consent recorded for every session
  6. Sessions stopped (creates DRAFT SOAP notes via stub)
  7. Each stub SOAP note is PATCHED with realistic clinical content
     (subjective / objective / assessment / plan + ICD + CPT)
  8. 8 of 18 notes approved, 2 marked EXPIRED, 2 pushed to FHIR
  9. 25–40 extra GETs to populate the audit log with varied traffic

Why PATCH? The /recordings/{id}/stop endpoint enqueues Celery for
transcription + SOAP generation; without real audio the AI sections remain
"Pending AI generation…". PATCH /notes/{id} accepts the same SOAPNoteEdit
schema the frontend uses and lets us drop in finished clinical prose.

Status flips (expired / fhir_pushed) and timestamp back-dating are not
exposed via the public API, so we perform a small direct DB pass at the
end using psycopg2 — purely for demo cosmetics.

Usage:
    python project-audit/seed_demo.py
    python project-audit/seed_demo.py --dry-run
    python project-audit/seed_demo.py --base http://localhost:8000/api/v1
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

# ────────────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(description="ClinNote AI investor-grade demo seed")
parser.add_argument("--base", default="http://localhost:8003/api/v1",
                    help="API base URL (default: http://localhost:8003/api/v1)")
parser.add_argument("--health", default=None,
                    help="Health URL (default: derived from --base)")
parser.add_argument("--dry-run", action="store_true",
                    help="Print what would be done without calling APIs")
parser.add_argument("--skip-db-tweaks", action="store_true",
                    help="Skip the direct-DB status flips (expired / fhir).")
parser.add_argument("--db-url", default=None,
                    help="Postgres sync URL (e.g. postgresql://clinnote:changeme@localhost:5432/clinnote_ai). "
                         "If omitted, derived from backend settings.")
args = parser.parse_args()

BASE = args.base.rstrip("/")
HEALTH = args.health or BASE.replace("/api/v1", "/health")
DRY_RUN = args.dry_run

# ────────────────────────────────────────────────────────────────────────────
# Constants
# ────────────────────────────────────────────────────────────────────────────

SPECIALTIES = [
    "Internal Medicine",
    "Cardiology",
    "Family Medicine",
    "Family Medicine",
    "Emergency Medicine",
    "Psychiatry",
]

CLINICIANS = [
    {
        "email": "dr.jones@clinnote-demo.com",
        "password": "Physician@Demo2024!",
        "first_name": "Sarah", "last_name": "Jones",
        "role": "physician", "specialty": "Internal Medicine",
        "npi_number": "1234567890", "org_id": "DEMO-ORG-001",
    },
    {
        "email": "dr.patel@clinnote-demo.com",
        "password": "Physician@Demo2024!",
        "first_name": "Priya", "last_name": "Patel",
        "role": "physician", "specialty": "Cardiology",
        "npi_number": "2345678901", "org_id": "DEMO-ORG-001",
    },
    {
        "email": "dr.rodriguez@clinnote-demo.com",
        "password": "Physician@Demo2024!",
        "first_name": "Carlos", "last_name": "Rodriguez",
        "role": "physician", "specialty": "Family Medicine",
        "npi_number": "3456789012", "org_id": "DEMO-ORG-001",
    },
    {
        "email": "dr.wilson@clinnote-demo.com",
        "password": "Physician@Demo2024!",
        "first_name": "Jessica", "last_name": "Wilson",
        "role": "physician", "specialty": "Family Medicine",
        "npi_number": "4567890123", "org_id": "DEMO-ORG-001",
    },
    {
        "email": "dr.webb@clinnote-demo.com",
        "password": "Physician@Demo2024!",
        "first_name": "Marcus", "last_name": "Webb",
        "role": "physician", "specialty": "Emergency Medicine",
        "npi_number": "5678901234", "org_id": "DEMO-ORG-001",
    },
    {
        "email": "dr.tanaka@clinnote-demo.com",
        "password": "Physician@Demo2024!",
        "first_name": "Yuki", "last_name": "Tanaka",
        "role": "physician", "specialty": "Psychiatry",
        "npi_number": "6789012345", "org_id": "DEMO-ORG-001",
    },
    {
        "email": "nurse.smith@clinnote-demo.com",
        "password": "Nurse@Demo2024!",
        "first_name": "Michael", "last_name": "Smith",
        "role": "nurse", "specialty": "Emergency",
        "org_id": "DEMO-ORG-001",
    },
]

PATIENTS = [
    {"mrn": "MRN-001001", "first_name": "Jane",     "last_name": "Doe",        "dob": "1985-03-22"},
    {"mrn": "MRN-001002", "first_name": "Robert",   "last_name": "Johnson",    "dob": "1952-08-14"},
    {"mrn": "MRN-001003", "first_name": "Maria",    "last_name": "Garcia",     "dob": "1978-11-05"},
    {"mrn": "MRN-001004", "first_name": "James",    "last_name": "Williams",   "dob": "1963-04-18"},
    {"mrn": "MRN-001005", "first_name": "Aisha",    "last_name": "Thompson",   "dob": "1990-07-29"},
    {"mrn": "MRN-001006", "first_name": "Wei",      "last_name": "Chen",       "dob": "1947-12-03"},
    {"mrn": "MRN-001007", "first_name": "Fatima",   "last_name": "Al-Hassan",  "dob": "1972-09-15"},
    {"mrn": "MRN-001008", "first_name": "David",    "last_name": "Nguyen",     "dob": "1988-02-07"},
    {"mrn": "MRN-001009", "first_name": "Sophia",   "last_name": "Martinez",   "dob": "1995-06-11"},
    {"mrn": "MRN-001010", "first_name": "Marcus",   "last_name": "Brown",      "dob": "1958-10-25"},
    {"mrn": "MRN-001011", "first_name": "Elena",    "last_name": "Kovacs",     "dob": "1969-01-30"},
    {"mrn": "MRN-001012", "first_name": "Samuel",   "last_name": "Okonkwo",    "dob": "1981-05-20"},
    {"mrn": "MRN-001013", "first_name": "Leila",    "last_name": "Ahmadi",     "dob": "2000-04-08"},
    {"mrn": "MRN-001014", "first_name": "Hiroshi",  "last_name": "Yamamoto",   "dob": "1942-09-19"},
    {"mrn": "MRN-001015", "first_name": "Olivia",   "last_name": "O'Sullivan", "dob": "1976-12-27"},
    {"mrn": "MRN-001016", "first_name": "Kwame",    "last_name": "Asante",     "dob": "1991-03-14"},
    {"mrn": "MRN-001017", "first_name": "Isabella", "last_name": "Rossi",      "dob": "1955-06-02"},
    {"mrn": "MRN-001018", "first_name": "Raj",      "last_name": "Sharma",     "dob": "1968-10-11"},
    {"mrn": "MRN-001019", "first_name": "Chloe",    "last_name": "Beaumont",   "dob": "2001-11-23"},
    {"mrn": "MRN-001020", "first_name": "Daniel",   "last_name": "Cohen",      "dob": "1947-07-16"},
]

# ────────────────────────────────────────────────────────────────────────────
# Six FULL SOAP templates
# ────────────────────────────────────────────────────────────────────────────

NOTE_CONTENTS: list[dict[str, Any]] = [
    {
        "label": "Type 2 Diabetes follow-up",
        "specialty": "Internal Medicine",
        "subjective": (
            "62-year-old male with history of Type 2 Diabetes Mellitus presents for routine follow-up. "
            "Reports good adherence to metformin 1000 mg BID. Denies polyuria, polydipsia, or polyphagia. "
            "Reports occasional fatigue in the afternoons. No chest pain, shortness of breath, or visual changes. "
            "Last HbA1c was 8.2% three months ago — patient acknowledges suboptimal glycemic control and "
            "admits to dietary indiscretion on weekends. Home glucose readings average 160–200 mg/dL fasting. "
            "No hypoglycemic episodes. Foot exam unremarkable to patient. No new medications since last visit."
        ),
        "objective": (
            "Vitals: BP 138/86, HR 78, RR 16, T 98.4°F, SpO2 98% on room air, weight 92.3 kg (BMI 31.4). "
            "General: alert, oriented x3, no acute distress. HEENT: PERRLA, oropharynx clear. "
            "CV: regular rate and rhythm, no murmurs, rubs, or gallops. Lungs: clear to auscultation bilaterally. "
            "Abdomen: soft, non-tender, no organomegaly. Extremities: no edema, intact dorsalis pedis pulses, "
            "monofilament 10/10 bilateral feet. Recent labs: HbA1c 8.2%, creatinine 1.0 mg/dL, "
            "eGFR 78 mL/min/1.73m², LDL 112 mg/dL, urine microalbumin 28 mg/g creatinine."
        ),
        "assessment": (
            "1. Type 2 Diabetes Mellitus, uncontrolled (E11.65) — HbA1c above target of 7.0%. "
            "2. Stage 1 Chronic Kidney Disease (N18.1) — eGFR 78 with microalbuminuria. "
            "3. Essential Hypertension (I10), suboptimally controlled at 138/86. "
            "4. Obesity, class 1 (E66.9) with BMI 31.4."
        ),
        "plan": (
            "1. Continue metformin 1000 mg BID. "
            "2. ADD empagliflozin 10 mg daily — cardiorenal protection and additional glycemic benefit. "
            "3. Continue lisinopril 20 mg daily; consider uptitration if BP remains above goal. "
            "4. Repeat HbA1c, BMP, and lipid panel in 12 weeks. "
            "5. Diabetes self-management education referral. "
            "6. Ophthalmology referral — overdue dilated retinal exam. "
            "7. Patient to log home glucose 4×/day for 2 weeks and bring journal to next visit. "
            "8. Follow up in 3 months."
        ),
        "icd_codes": [
            {"code": "E11.65", "description": "Type 2 diabetes mellitus with hyperglycemia",        "confidence": 0.96, "is_primary": True},
            {"code": "I10",    "description": "Essential (primary) hypertension",                    "confidence": 0.94, "is_primary": False},
            {"code": "N18.1",  "description": "Chronic kidney disease, stage 1",                     "confidence": 0.81, "is_primary": False},
            {"code": "E66.9",  "description": "Obesity, unspecified",                                "confidence": 0.88, "is_primary": False},
        ],
        "cpt_codes": [
            {"code": "99214", "description": "Office/outpatient visit, est patient, moderate complexity", "confidence": 0.91},
            {"code": "36415", "description": "Routine venipuncture",                                       "confidence": 0.95},
        ],
    },
    {
        "label": "Acute chest pain — non-cardiac",
        "specialty": "Cardiology",
        "subjective": (
            "54-year-old female referred for evaluation of intermittent chest pain over the past 2 weeks. "
            "Describes a sharp, left-sided substernal pain lasting 5–10 minutes, reproducible with deep "
            "inspiration and palpation of the chest wall. Pain is not exertional and resolves with rest. "
            "Denies radiation to arm or jaw, diaphoresis, nausea, or dyspnea. No prior cardiac history. "
            "Family history: father had MI at age 67. Patient has been under significant work stress and "
            "recently started CrossFit-style training. No medication changes. Tobacco: never. Alcohol: 2–3 "
            "drinks/week. Denies recreational drug use."
        ),
        "objective": (
            "Vitals: BP 124/78, HR 72, RR 14, T 98.1°F, SpO2 99% on RA. "
            "General: well-appearing, no distress. Cardiac: RRR, normal S1/S2, no murmurs/rubs/gallops, "
            "no JVD. Reproducible tenderness over left costochondral junctions 4–5. Lungs clear bilaterally. "
            "ECG: normal sinus rhythm, rate 72, no ST changes, no Q waves, normal axis and intervals. "
            "Troponin I: <0.012 ng/mL (negative). CBC, BMP unremarkable. Lipid panel: LDL 118, HDL 56, TG 102. "
            "Stress echo (yesterday): negative for inducible ischemia, normal LV function (EF 62%)."
        ),
        "assessment": (
            "1. Costochondritis (M94.0) — reproducible chest wall tenderness; high-probability musculoskeletal "
            "etiology in the setting of recent intense exercise. "
            "2. Chest pain, ruled out cardiac etiology (R07.9) — negative biomarkers, normal ECG, negative "
            "stress echo. "
            "3. Anxiety, situational (F41.9) — likely contributor."
        ),
        "plan": (
            "1. Reassurance — cardiac workup is negative. "
            "2. Ibuprofen 600 mg PO TID with food x 7 days for costochondritis. "
            "3. Modify exercise: pause CrossFit, switch to low-impact cardio for 2 weeks. "
            "4. Return precautions: any exertional chest pain, syncope, or pain radiating to jaw/arm — call 911. "
            "5. Lifestyle counseling: stress management, sleep hygiene. "
            "6. Follow up with PCP in 4 weeks. No further cardiology follow-up needed unless symptoms recur."
        ),
        "icd_codes": [
            {"code": "M94.0", "description": "Chondrocostal junction syndrome (Tietze)", "confidence": 0.89, "is_primary": True},
            {"code": "R07.9", "description": "Chest pain, unspecified",                  "confidence": 0.82, "is_primary": False},
            {"code": "F41.9", "description": "Anxiety disorder, unspecified",            "confidence": 0.71, "is_primary": False},
        ],
        "cpt_codes": [
            {"code": "99244", "description": "Office consultation, moderate-high complexity", "confidence": 0.90},
            {"code": "93306", "description": "Echocardiography, transthoracic, complete",     "confidence": 0.93},
            {"code": "93000", "description": "Electrocardiogram with interpretation",         "confidence": 0.97},
        ],
    },
    {
        "label": "Hypertension management",
        "specialty": "Family Medicine",
        "subjective": (
            "48-year-old male presents for 3-month follow-up of essential hypertension. Reports good "
            "adherence to amlodipine 5 mg daily and HCTZ 25 mg daily. Home BP log shows readings between "
            "140–155/90–96 over the past month — patient measures BP twice daily on a validated home cuff. "
            "Denies headaches, visual changes, palpitations, or chest pain. Reports modestly improved diet "
            "but still struggles with sodium intake (frequent takeout). Walks 30 minutes 4×/week. "
            "Sleep: 6–7 hours/night, snoring per spouse. No medication side effects."
        ),
        "objective": (
            "Vitals: BP 148/94 (right arm, sitting, repeated 5 min later 146/92), HR 76, RR 14, T 98.2°F, "
            "weight 88.1 kg (BMI 28.7). General: well-appearing. CV: RRR, no murmurs. Lungs: clear. "
            "Abdomen: soft, no bruits. Extremities: no edema, equal pulses. Fundoscopic: no AV nicking. "
            "Recent labs: BMP normal, eGFR 92, urine microalbumin negative, lipid panel: LDL 134, "
            "HDL 42, TG 168. HbA1c 5.7% (prediabetes range). TSH 1.8 (normal). EKG: NSR, no LVH."
        ),
        "assessment": (
            "1. Essential Hypertension (I10), uncontrolled — average BP 148/93 above goal <130/80 per "
            "ACC/AHA 2017 guidelines. "
            "2. Prediabetes (R73.03) — HbA1c 5.7%. "
            "3. Mixed hyperlipidemia (E78.2) — LDL above optimal. "
            "4. Overweight (E66.3) with BMI 28.7. "
            "5. Possible obstructive sleep apnea (G47.30) — snoring history, untreated."
        ),
        "plan": (
            "1. Increase amlodipine to 10 mg daily; continue HCTZ 25 mg daily. "
            "2. ADD losartan 50 mg daily — ARB for additional BP control and cardio-renal protection. "
            "3. DASH diet counseling, target sodium <2 g/day; nutrition referral placed. "
            "4. Start atorvastatin 20 mg nightly for primary prevention (ASCVD 10-yr risk 12.4%). "
            "5. Home BP log to continue — bring to next visit. "
            "6. Sleep study referral (suspected OSA). "
            "7. Repeat BMP in 2 weeks (HCTZ + losartan combination). "
            "8. Follow up in 4 weeks."
        ),
        "icd_codes": [
            {"code": "I10",    "description": "Essential (primary) hypertension",   "confidence": 0.97, "is_primary": True},
            {"code": "E78.2",  "description": "Mixed hyperlipidemia",               "confidence": 0.90, "is_primary": False},
            {"code": "R73.03", "description": "Prediabetes",                        "confidence": 0.87, "is_primary": False},
            {"code": "E66.3",  "description": "Overweight",                         "confidence": 0.79, "is_primary": False},
            {"code": "G47.30", "description": "Sleep apnea, unspecified",           "confidence": 0.65, "is_primary": False},
        ],
        "cpt_codes": [
            {"code": "99214", "description": "Office/outpatient visit, est patient, moderate complexity", "confidence": 0.92},
            {"code": "93000", "description": "Electrocardiogram with interpretation",                     "confidence": 0.94},
        ],
    },
    {
        "label": "Asthma exacerbation",
        "specialty": "Family Medicine",
        "subjective": (
            "9-year-old female with known mild persistent asthma presents with 3 days of progressive cough, "
            "wheezing, and shortness of breath. Symptoms worse at night and with exercise. Albuterol HFA "
            "use has increased to every 3–4 hours with partial relief. Mother reports recent URI in the "
            "household. No fever, chest pain, or cyanosis. Patient is on fluticasone 88 mcg BID maintenance "
            "but adherence has been inconsistent. No known new allergen exposures. Last hospitalization for "
            "asthma: 2 years ago, no ICU admissions. Up to date on immunizations. No pets at home."
        ),
        "objective": (
            "Vitals: T 99.1°F, HR 108, RR 28, BP 102/64, SpO2 93% on room air, weight 32 kg. "
            "General: alert, mild respiratory distress, able to speak in 3–4 word sentences. "
            "HEENT: clear rhinorrhea, oropharynx mildly erythematous. Neck: supple, no lymphadenopathy. "
            "Lungs: diffuse expiratory wheeze bilaterally, prolonged expiratory phase, mild subcostal "
            "retractions. CV: tachycardic, regular, no murmurs. Peak flow: 60% of personal best. "
            "After 3 albuterol nebs and 1 dose oral dexamethasone in clinic: SpO2 97%, RR 22, "
            "wheeze markedly reduced, peak flow 85% of personal best."
        ),
        "assessment": (
            "1. Acute asthma exacerbation, moderate (J45.901) — triggered by viral URI; responded well to "
            "in-clinic bronchodilator + systemic steroid. "
            "2. Mild persistent asthma, poorly controlled (J45.30) — frequent rescue inhaler use, suboptimal "
            "controller adherence. "
            "3. Viral upper respiratory infection (J06.9)."
        ),
        "plan": (
            "1. Dexamethasone 0.6 mg/kg PO x 1 dose (given in clinic), then 0.6 mg/kg PO tomorrow morning. "
            "2. Albuterol HFA 2 puffs every 4 hours PRN x 5 days, then taper. "
            "3. INCREASE controller: fluticasone 110 mcg BID via spacer x 4 weeks. "
            "4. Asthma action plan reviewed and updated with family. "
            "5. Spacer technique demonstrated; family return-demo confirmed. "
            "6. Return precautions: SpO2 <92%, inability to speak in full sentences, no relief from albuterol — "
            "go to ED. "
            "7. Follow up in 1 week to reassess; pulmonary function testing at next visit if age-appropriate."
        ),
        "icd_codes": [
            {"code": "J45.901", "description": "Unspecified asthma with (acute) exacerbation", "confidence": 0.96, "is_primary": True},
            {"code": "J45.30",  "description": "Mild persistent asthma, uncomplicated",         "confidence": 0.85, "is_primary": False},
            {"code": "J06.9",   "description": "Acute upper respiratory infection, unspecified","confidence": 0.78, "is_primary": False},
        ],
        "cpt_codes": [
            {"code": "99214", "description": "Office/outpatient visit, est patient, moderate complexity", "confidence": 0.93},
            {"code": "94640", "description": "Pressurized or non-pressurized nebulizer treatment",        "confidence": 0.97},
            {"code": "94760", "description": "Pulse oximetry, single determination",                       "confidence": 0.95},
        ],
    },
    {
        "label": "Anxiety with comorbid depression",
        "specialty": "Psychiatry",
        "subjective": (
            "34-year-old female presents for psychiatric evaluation with 6 months of escalating anxiety and "
            "low mood. Reports daily worry that is difficult to control, restlessness, muscle tension, "
            "and frequent early morning awakening (3–4 AM). Describes anhedonia, fatigue, decreased "
            "concentration at work, and 4 kg unintentional weight loss. Denies suicidal ideation, intent, "
            "or plan, but acknowledges occasional passive thoughts that 'life feels heavy.' No prior "
            "psychiatric diagnoses or medications. No substance use. Family history of major depressive "
            "disorder (mother). Recent stressor: divorce 8 months ago. PHQ-9 score: 16 (moderate-severe). "
            "GAD-7 score: 15 (severe)."
        ),
        "objective": (
            "Vitals: BP 118/72, HR 84, RR 16, T 98.0°F, weight 58 kg (lost 4 kg in 6 mo). "
            "General appearance: well-groomed but appears tired. "
            "Mental Status Exam: alert, fully oriented. Mood: 'low and anxious.' Affect: constricted, "
            "congruent. Speech: normal rate and rhythm. Thought process: linear, goal-directed. "
            "Thought content: no delusions, no SI/HI/AVH. Insight and judgment: good. "
            "Cognition grossly intact. TSH, B12, CBC, CMP within normal limits."
        ),
        "assessment": (
            "1. Major Depressive Disorder, single episode, moderate (F32.1) — meets DSM-5 criteria with "
            "depressed mood, anhedonia, weight loss, insomnia, fatigue, and impaired concentration for "
            ">2 weeks. "
            "2. Generalized Anxiety Disorder (F41.1) — GAD-7 of 15, symptoms present >6 months. "
            "3. Adjustment difficulties post-divorce (Z63.5)."
            " Suicide risk: LOW — passive ideation, no intent, no plan, good protective factors (employment, "
            "family support, future-oriented)."
        ),
        "plan": (
            "1. Start sertraline 25 mg PO daily x 7 days, then increase to 50 mg daily. "
            "2. Counsel on SSRI side effects, 2–4 week onset, and discontinuation syndrome. "
            "3. Refer to weekly CBT — addresses both anxiety and depression. "
            "4. Sleep hygiene education provided in session. "
            "5. Safety plan completed: crisis line 988 written and verbalized. Patient agrees to contact "
            "crisis services or come to ED if SI escalates. "
            "6. PHQ-9 and GAD-7 to be repeated at every visit. "
            "7. Follow up in 2 weeks to assess tolerance and titration."
        ),
        "icd_codes": [
            {"code": "F32.1", "description": "Major depressive disorder, single episode, moderate", "confidence": 0.94, "is_primary": True},
            {"code": "F41.1", "description": "Generalized anxiety disorder",                        "confidence": 0.93, "is_primary": False},
            {"code": "Z63.5", "description": "Disruption of family by separation/divorce",           "confidence": 0.81, "is_primary": False},
        ],
        "cpt_codes": [
            {"code": "90792", "description": "Psychiatric diagnostic evaluation with medical services", "confidence": 0.96},
            {"code": "90833", "description": "Psychotherapy, 30 minutes, with E/M",                     "confidence": 0.74},
        ],
    },
    {
        "label": "Sprained ankle",
        "specialty": "Emergency Medicine",
        "subjective": (
            "28-year-old male presents to the Emergency Department with right ankle pain after twisting his "
            "ankle during a recreational soccer game 2 hours ago. Felt a 'pop,' immediate pain, and was "
            "unable to bear weight afterward. Pain rated 7/10, sharp, worse with movement, improves with "
            "elevation. No prior ankle injuries. Denies numbness, tingling, or color changes in foot. "
            "No head injury, neck pain, or loss of consciousness. Last tetanus 4 years ago. "
            "No medications, no allergies. Otherwise healthy."
        ),
        "objective": (
            "Vitals: BP 128/76, HR 88, RR 14, T 98.4°F, SpO2 99% on RA. "
            "Right ankle: marked swelling and ecchymosis over the lateral malleolus, tenderness over the "
            "ATFL and CFL, no tenderness over the medial malleolus or proximal fibula. Range of motion "
            "limited by pain in all planes. Unable to bear weight x 4 steps. Distal neurovascular intact: "
            "2+ dorsalis pedis pulse, capillary refill <2 sec, sensation intact, motor 5/5. "
            "Ottawa Ankle Rules: positive — unable to bear weight + lateral malleolus tenderness. "
            "X-ray right ankle (3 views): no acute fracture; soft-tissue swelling over lateral malleolus."
        ),
        "assessment": (
            "1. Right ankle sprain, lateral ligament complex, grade II (S93.401A) — ATFL + CFL involvement, "
            "no fracture on radiograph. "
            "2. Pain, acute (G89.11)."
        ),
        "plan": (
            "1. RICE protocol: rest, ice 20 minutes 4×/day, compression with ACE wrap, elevation. "
            "2. Aircast stirrup brace dispensed in ED — wear during all weight-bearing for 4 weeks. "
            "3. Crutches with partial weight-bearing as tolerated x 5–7 days. "
            "4. Ibuprofen 600 mg PO TID with food x 5 days; acetaminophen 1000 mg q6h PRN for breakthrough. "
            "5. Begin gentle ankle ROM exercises in 48–72 hours. "
            "6. Return precautions: worsening pain, numbness, color change, inability to wiggle toes — return "
            "to ED. "
            "7. Follow up with primary care or orthopedics in 7–10 days if not improving. "
            "8. Work/school note provided: light duty x 1 week."
        ),
        "icd_codes": [
            {"code": "S93.401A", "description": "Sprain of unspecified ligament of right ankle, initial encounter", "confidence": 0.95, "is_primary": True},
            {"code": "G89.11",   "description": "Acute pain due to trauma",                                          "confidence": 0.82, "is_primary": False},
        ],
        "cpt_codes": [
            {"code": "99284", "description": "Emergency department visit, moderate complexity",   "confidence": 0.93},
            {"code": "73610", "description": "Radiologic exam, ankle; complete, minimum 3 views", "confidence": 0.97},
            {"code": "29515", "description": "Application of short leg splint (calf to foot)",    "confidence": 0.88},
        ],
    },
]


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def check(resp: requests.Response, label: str) -> Any:
    if resp.status_code not in (200, 201):
        print(f"  x {label}: {resp.status_code} - {resp.text[:200]}")
        return None
    try:
        data = resp.json()
    except Exception:
        data = {}
    print(f"  + {label}")
    return data


def safe_request(method: str, url: str, **kw) -> requests.Response | None:
    """requests.request that doesn't raise — returns None on hard failure."""
    if DRY_RUN:
        print(f"  [dry-run] {method} {url}")
        return None
    try:
        return requests.request(method, url, timeout=30, **kw)
    except Exception as exc:
        print(f"  x {method} {url} - exception: {exc}")
        return None


def patch_soap(note_id: str, content: dict[str, Any], token: str) -> bool:
    """
    PATCH /notes/{note_id} with subjective/objective/assessment/plan +
    icd_codes + cpt_codes. Returns True on 2xx, False otherwise.
    """
    payload = {
        "subjective": content["subjective"],
        "objective":  content["objective"],
        "assessment": content["assessment"],
        "plan":       content["plan"],
        "icd_codes":  content["icd_codes"],
        "cpt_codes":  content["cpt_codes"],
    }
    resp = safe_request("PATCH", f"{BASE}/notes/{note_id}",
                        json=payload, headers=headers(token))
    if resp is None:
        return False
    if resp.status_code in (200, 201):
        return True
    print(f"    ! PATCH /notes/{note_id} returned {resp.status_code} - {resp.text[:200]}")
    return False


def seed_audit_traffic(tokens: list[str], patient_ids: list[str],
                       session_ids: list[str], note_ids: list[str],
                       count: int = 30) -> int:
    """
    Generate varied GETs to populate the audit log with diverse actions,
    users, and resources. Returns the number of successful requests.
    """
    if not tokens:
        return 0
    actions = []
    for pid in patient_ids:
        if pid:
            actions.append(("GET", f"{BASE}/patients/{pid}"))
    for sid in session_ids:
        if sid:
            actions.append(("GET", f"{BASE}/recordings/{sid}"))
            actions.append(("GET", f"{BASE}/transcripts/session/{sid}"))
    for nid in note_ids:
        if nid:
            actions.append(("GET", f"{BASE}/notes/{nid}"))
    # Light dashboard endpoints
    for _ in range(8):
        actions.append(("GET", f"{BASE}/patients?page=1&page_size=20"))
        actions.append(("GET", f"{BASE}/notes?page=1&page_size=20"))
        actions.append(("GET", f"{BASE}/recordings?limit=20"))

    random.shuffle(actions)
    actions = actions[:count]

    ok = 0
    for method, url in actions:
        tok = random.choice(tokens)
        resp = safe_request(method, url, headers=headers(tok))
        if resp is not None and resp.status_code in (200, 201, 404):
            ok += 1
    return ok


def random_past_timestamps(n: int, days_back: int = 30) -> list[datetime]:
    """
    Return n unique timestamps, each at a distinct minute-of-day,
    spread across the last `days_back` days.
    """
    out: list[datetime] = []
    seen_minute_keys: set[str] = set()
    now = datetime.now(timezone.utc)
    safety = 0
    while len(out) < n and safety < n * 50:
        safety += 1
        days_off = random.randint(0, days_back - 1)
        hour = random.choice([8, 9, 10, 11, 13, 14, 15, 16, 17])
        minute = random.choice([3, 8, 14, 22, 25, 31, 37, 42, 47, 53, 58])
        ts = (now - timedelta(days=days_off)).replace(
            hour=hour, minute=minute, second=random.randint(0, 59), microsecond=0
        )
        key = ts.strftime("%Y-%m-%d %H:%M")
        if key in seen_minute_keys:
            continue
        seen_minute_keys.add(key)
        out.append(ts)
    out.sort()
    return out


# ────────────────────────────────────────────────────────────────────────────
# 0. Health check
# ────────────────────────────────────────────────────────────────────────────

print("=== ClinNote AI Demo Seed (investor-grade) ===")
print(f"BASE   = {BASE}")
print(f"HEALTH = {HEALTH}")
print(f"DRY    = {DRY_RUN}")

if not DRY_RUN:
    try:
        h = requests.get(HEALTH, timeout=5)
        print(f"Health: {h.json()}")
    except Exception as e:
        print(f"Backend not reachable: {e}")
        sys.exit(1)

# ────────────────────────────────────────────────────────────────────────────
# Step A — Bootstrap admin
# ────────────────────────────────────────────────────────────────────────────

print("\n[A] Admin bootstrap (Alexandra Chen)")
admin_payload = {
    "email": "admin@clinnote-demo.com",
    "password": "Admin@ClinNote2024!",
    "first_name": "Alexandra",
    "last_name": "Chen",
    "role": "admin",
}
resp = safe_request("POST", f"{BASE}/auth/bootstrap", json=admin_payload)
if resp is not None:
    if resp.status_code == 201:
        print("  + Admin bootstrapped")
    elif "already exist" in (resp.text or "").lower():
        print("  + Admin already exists")
    else:
        print(f"  ? Bootstrap: {resp.status_code} - {resp.text[:200]}")

resp = safe_request("POST", f"{BASE}/auth/login",
                    json={"email": admin_payload["email"],
                          "password": admin_payload["password"]})
if DRY_RUN:
    admin_token = "DRY-RUN-ADMIN"
else:
    admin_data = check(resp, "Admin login") if resp else None
    if not admin_data:
        print("Admin login failed - abort"); sys.exit(1)
    admin_token = admin_data["access_token"]

# ────────────────────────────────────────────────────────────────────────────
# Step B — Register 6 physicians + 1 nurse
# ────────────────────────────────────────────────────────────────────────────

print("\n[B] Register clinical users")
for u in CLINICIANS:
    resp = safe_request("POST", f"{BASE}/auth/register",
                        json=u, headers=headers(admin_token))
    if resp is None:
        continue
    if resp.status_code == 201:
        print(f"  + Created: {u['email']}")
    elif "already" in (resp.text or "").lower() or resp.status_code == 409:
        print(f"  + Exists:  {u['email']}")
    else:
        print(f"  x Failed:  {u['email']} - {resp.status_code}: {resp.text[:100]}")

# Login each physician (skip nurse — nurses cannot record per backend rules)
phys_tokens: dict[str, str] = {}
for u in CLINICIANS:
    if u["role"] != "physician":
        continue
    resp = safe_request("POST", f"{BASE}/auth/login",
                        json={"email": u["email"], "password": u["password"]})
    if DRY_RUN:
        phys_tokens[u["email"]] = f"DRY-{u['email']}"
        continue
    if resp is None:
        continue
    if resp.status_code == 200:
        phys_tokens[u["email"]] = resp.json()["access_token"]
        print(f"  + Logged in: {u['email']}")
    else:
        print(f"  x Login failed: {u['email']} - {resp.status_code}")

if not phys_tokens and not DRY_RUN:
    print("No physician tokens obtained - abort"); sys.exit(1)

# Default token = Dr. Jones (Internal Medicine)
dr_token = phys_tokens.get("dr.jones@clinnote-demo.com") or next(iter(phys_tokens.values()), "DRY")

# ────────────────────────────────────────────────────────────────────────────
# Step C — 20 patients
# ────────────────────────────────────────────────────────────────────────────

print("\n[C] Create 20 patients")
patient_ids: list[str | None] = []
for i, p in enumerate(PATIENTS):
    payload = {
        **p,
        "encounter_id": f"ENC-{10001 + i}",
        "org_id": "DEMO-ORG-001",
    }
    resp = safe_request("POST", f"{BASE}/patients",
                        json=payload, headers=headers(dr_token))
    if resp is None:
        patient_ids.append(None); continue
    if resp.status_code == 201:
        pid = resp.json()["id"]
        patient_ids.append(pid)
        print(f"  + {p['mrn']}: {p['first_name']} {p['last_name']}")
    else:
        # Try fetch existing
        resp2 = safe_request("GET", f"{BASE}/patients/mrn/{p['mrn']}",
                             headers=headers(dr_token))
        if resp2 is not None and resp2.status_code == 200:
            pid = resp2.json()["id"]
            patient_ids.append(pid)
            print(f"  + {p['mrn']} (existed): {p['first_name']} {p['last_name']}")
        else:
            print(f"  x {p['mrn']}: {resp.status_code} - {resp.text[:100]}")
            patient_ids.append(None)

# ────────────────────────────────────────────────────────────────────────────
# Step D — 18 recording sessions, staggered timestamps
# ────────────────────────────────────────────────────────────────────────────

N_SESSIONS = 18
print(f"\n[D] Create {N_SESSIONS} recording sessions (staggered)")

# Pair each session with a patient (cycle through 20) and a template (cycle 6),
# and a physician matching that template's specialty when possible.
phys_by_specialty: dict[str, str] = {}
for u in CLINICIANS:
    if u["role"] == "physician":
        tok = phys_tokens.get(u["email"])
        if tok:
            phys_by_specialty.setdefault(u["specialty"], tok)

session_records: list[dict[str, Any]] = []
for i in range(N_SESSIONS):
    patient_idx = i % len(PATIENTS)
    template_idx = i % len(NOTE_CONTENTS)
    template = NOTE_CONTENTS[template_idx]
    token = phys_by_specialty.get(template["specialty"], dr_token)
    session_records.append({
        "idx": i,
        "patient_idx": patient_idx,
        "patient_mrn": PATIENTS[patient_idx]["mrn"],
        "patient_name": f"{PATIENTS[patient_idx]['first_name']} {PATIENTS[patient_idx]['last_name']}",
        "patient_id": patient_ids[patient_idx] if patient_idx < len(patient_ids) else None,
        "template": template,
        "token": token,
        "scheduled_at": None,  # filled below
        "session_id": None,
        "note_id": None,
    })

# Assign staggered timestamps (one per session)
timestamps = random_past_timestamps(N_SESSIONS, days_back=30)
for s, ts in zip(session_records, timestamps):
    s["scheduled_at"] = ts

# Create the sessions
for s in session_records:
    payload = {
        "patient_mrn": s["patient_mrn"],
        "encounter_id": f"ENC-{20001 + s['idx']}",
        "session_metadata": {
            "specialty": s["template"]["specialty"],
            "room": f"Exam-{(s['idx'] % 8) + 1}",
            "demo_template": s["template"]["label"],
            "demo_scheduled_at": s["scheduled_at"].isoformat(),
        },
    }
    resp = safe_request("POST", f"{BASE}/recordings/start",
                        json=payload, headers=headers(s["token"]))
    if resp is None:
        continue
    if resp.status_code == 201:
        sid = resp.json().get("id") or resp.json().get("session_id")
        s["session_id"] = sid
        print(f"  + Session {s['idx']+1:02d} | {s['template']['specialty']:18s} | "
              f"{s['patient_name']:22s} | {s['scheduled_at'].strftime('%Y-%m-%d %H:%M')}")
    else:
        print(f"  x Session {s['idx']+1}: {resp.status_code} - {resp.text[:150]}")

# ────────────────────────────────────────────────────────────────────────────
# Step E — Consent
# ────────────────────────────────────────────────────────────────────────────

print("\n[E] Record consent")
for s in session_records:
    if not s["session_id"]:
        continue
    payload = {
        "session_id": s["session_id"],
        "consent_type": "verbal",
        "notes": f"{s['patient_name']} verbally confirmed consent to ambient recording",
    }
    resp = safe_request("POST", f"{BASE}/consent/record",
                        json=payload, headers=headers(s["token"]))
    if resp is None:
        continue
    if resp.status_code in (200, 201):
        pass
    else:
        print(f"  x Consent {s['idx']+1}: {resp.status_code} - {resp.text[:100]}")
print(f"  + Consent recorded for {sum(1 for s in session_records if s['session_id'])} sessions")

# ────────────────────────────────────────────────────────────────────────────
# Step F — Stop sessions (creates stub DRAFT SOAP note)
# ────────────────────────────────────────────────────────────────────────────

print("\n[F] Stop sessions (creates DRAFT SOAP note stubs)")
for s in session_records:
    if not s["session_id"]:
        continue
    resp = safe_request("POST", f"{BASE}/recordings/{s['session_id']}/stop",
                        headers=headers(s["token"]))
    if resp is None:
        continue
    if resp.status_code in (200, 201):
        try:
            data = resp.json()
            s["note_id"] = data.get("note_id")
        except Exception:
            s["note_id"] = None
    else:
        print(f"  x Stop {s['idx']+1}: {resp.status_code} - {resp.text[:100]}")
print(f"  + Stopped {sum(1 for s in session_records if s['note_id'])} sessions with note_id")

# If note_id wasn't returned, look it up via /notes
if not DRY_RUN:
    missing = [s for s in session_records if s["session_id"] and not s["note_id"]]
    if missing:
        # Use admin to list all notes for resolution
        resp = safe_request("GET", f"{BASE}/notes?page_size=200",
                            headers=headers(admin_token))
        if resp is not None and resp.status_code == 200:
            try:
                items = resp.json().get("data", [])
                by_session = {r["session_id"]: r["id"] for r in items}
                for s in missing:
                    s["note_id"] = by_session.get(str(s["session_id"]))
            except Exception:
                pass

# ────────────────────────────────────────────────────────────────────────────
# Step G — PATCH each SOAP note with the realistic template content
# ────────────────────────────────────────────────────────────────────────────

print("\n[G] PATCH each SOAP note with realistic clinical content")
patched = 0
for s in session_records:
    if not s["note_id"]:
        continue
    ok = patch_soap(s["note_id"], s["template"], s["token"])
    if ok:
        patched += 1
        print(f"  + Note {s['idx']+1:02d} patched ({s['template']['label']})")
    else:
        print(f"  ! Note {s['idx']+1:02d} PATCH failed - investigate /notes/{s['note_id']}")
print(f"  Patched {patched} / {len(session_records)} notes")

# ────────────────────────────────────────────────────────────────────────────
# Step H — Approve 8 of 18 notes
# ────────────────────────────────────────────────────────────────────────────

print("\n[H] Approve 8 of 18 notes")
approved = 0
notes_with_id = [s for s in session_records if s["note_id"]]
# Pick first 8 (deterministic for demo reproducibility)
for s in notes_with_id[:8]:
    payload = {"attestation": "I attest that this note accurately reflects the clinical encounter."}
    resp = safe_request("POST", f"{BASE}/notes/{s['note_id']}/approve",
                        json=payload, headers=headers(s["token"]))
    if resp is None:
        continue
    if resp.status_code in (200, 201):
        approved += 1
        print(f"  + Approved note {s['idx']+1:02d}")
    else:
        print(f"  x Approve {s['idx']+1}: {resp.status_code} - {resp.text[:120]}")
print(f"  Approved {approved} notes")

# ────────────────────────────────────────────────────────────────────────────
# Step I + J — DB tweaks: 2 expired, 2 FHIR-pushed, back-date timestamps
# ────────────────────────────────────────────────────────────────────────────

# These cosmetic flips are not exposed via the public API; do them with a
# direct DB connection. Skipped if --skip-db-tweaks or no psycopg2.

did_db_tweaks = False
if not args.skip_db_tweaks and not DRY_RUN:
    print("\n[I/J] Direct DB tweaks: expired / fhir status + back-dated timestamps")
    # Resolve DB URL up front so we can pick the right driver.
    _resolved_db_url = args.db_url
    if not _resolved_db_url:
        try:
            import os
            candidates = [
                os.environ.get("DATABASE_URL_SYNC"),
                os.environ.get("DATABASE_URL"),
                "postgresql://clinnote:changeme@localhost:5432/clinnote_ai",
                "postgresql://postgres:postgres@localhost:5433/clinnote_ai",
            ]
            _resolved_db_url = next((c for c in candidates if c), None)
        except Exception:
            pass

    _is_sqlite = (
        _resolved_db_url is not None
        and (
            _resolved_db_url.startswith("sqlite")
            or _resolved_db_url.startswith("sqlite+aiosqlite:///")
        )
    )

    if _is_sqlite:
        # SQLite branch — stdlib sqlite3 (no extra deps). Back-date timestamps,
        # mark expired / fhir-pushed exactly like the Postgres branch.
        import sqlite3
        # Strip async driver prefix and resolve to a real file path
        sqlite_path = _resolved_db_url
        for prefix in ("sqlite+aiosqlite:///", "sqlite+pysqlite:///", "sqlite:///"):
            if sqlite_path.startswith(prefix):
                sqlite_path = sqlite_path[len(prefix):]
                break
        try:
            conn = sqlite3.connect(sqlite_path)
            cur = conn.cursor()

            pending = [s for s in notes_with_id[8:]]
            expired_targets = pending[-2:] if len(pending) >= 2 else pending
            for s in expired_targets:
                cur.execute(
                    "UPDATE soap_notes SET status='expired', "
                    "expires_at = datetime('now', '-1 hour') WHERE id = ?",
                    (str(s["note_id"]),),
                )
                print(f"  + Marked note {s['idx']+1:02d} as EXPIRED")

            fhir_targets = notes_with_id[:2]
            for k, s in enumerate(fhir_targets):
                fake_urn = f"urn:fhir:DocumentReference:demo-{s['idx']+1:02d}-{int(time.time())}"
                cur.execute(
                    "UPDATE soap_notes SET fhir_push_status='success', "
                    "fhir_resource_id=? WHERE id = ?",
                    (fake_urn, str(s["note_id"])),
                )
                print(f"  + Marked note {s['idx']+1:02d} as FHIR-pushed ({fake_urn})")

            # Back-date created_at / updated_at on sessions + notes so the
            # dashboard shows realistic spread.
            for s in session_records:
                if not s["session_id"] or not s["scheduled_at"]:
                    continue
                ts = s["scheduled_at"].strftime("%Y-%m-%d %H:%M:%S")
                end_ts = (s["scheduled_at"] + timedelta(minutes=14)).strftime("%Y-%m-%d %H:%M:%S")
                note_created = (s["scheduled_at"] + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
                note_updated = (s["scheduled_at"] + timedelta(minutes=20)).strftime("%Y-%m-%d %H:%M:%S")
                cur.execute(
                    "UPDATE recording_sessions SET created_at = ?, "
                    "start_time = ?, end_time = ? WHERE id = ?",
                    (ts, ts, end_ts, str(s["session_id"])),
                )
                if s["note_id"]:
                    cur.execute(
                        "UPDATE soap_notes SET created_at = ?, updated_at = ? "
                        "WHERE id = ?",
                        (note_created, note_updated, str(s["note_id"])),
                    )

            conn.commit()
            cur.close()
            conn.close()
            did_db_tweaks = True
            print(f"  + SQLite DB tweaks applied ({sqlite_path})")
        except Exception as exc:
            print(f"  ! SQLite DB tweak failed: {exc}")
        # Skip the Postgres branch below
        psycopg2 = None  # type: ignore
    else:
        try:
            import psycopg2  # type: ignore
        except ImportError:
            print("  ! psycopg2 not installed - skipping DB tweaks. "
                  "Install with: pip install psycopg2-binary")
            psycopg2 = None  # type: ignore

    if psycopg2 is not None:
        db_url = args.db_url
        if not db_url:
            # Try to read backend settings
            try:
                import os
                # Common dev defaults
                candidates = [
                    os.environ.get("DATABASE_URL_SYNC"),
                    "postgresql://clinnote:changeme@localhost:5432/clinnote_ai",
                    "postgresql://postgres:postgres@localhost:5433/clinnote_ai",
                ]
                db_url = next((c for c in candidates if c), None)
            except Exception:
                pass

        if not db_url:
            print("  ! No DB URL available - skipping. Pass --db-url postgresql://...")
        else:
            # Replace asyncpg driver tag if present (sync driver expected)
            db_url = (db_url.replace("postgresql+asyncpg://", "postgresql://")
                            .replace("postgresql+psycopg://", "postgresql://"))
            try:
                conn = psycopg2.connect(db_url)
                conn.autocommit = True
                cur = conn.cursor()

                # 2 expired notes — pick the last two un-approved ones
                pending = [s for s in notes_with_id[8:]]
                expired_targets = pending[-2:] if len(pending) >= 2 else pending
                for s in expired_targets:
                    cur.execute(
                        "UPDATE soap_notes SET status='expired', expires_at = NOW() - INTERVAL '1 hour' "
                        "WHERE id = %s",
                        (str(s["note_id"]),),
                    )
                    print(f"  + Marked note {s['idx']+1:02d} as EXPIRED")

                # 2 FHIR-pushed — pick first two approved
                fhir_targets = notes_with_id[:2]
                for k, s in enumerate(fhir_targets):
                    fake_urn = f"urn:fhir:DocumentReference:demo-{s['idx']+1:02d}-{int(time.time())}"
                    cur.execute(
                        "UPDATE soap_notes SET fhir_push_status='success', fhir_resource_id=%s "
                        "WHERE id = %s",
                        (fake_urn, str(s["note_id"])),
                    )
                    print(f"  + Marked note {s['idx']+1:02d} as FHIR-pushed ({fake_urn})")

                # Back-date created_at / updated_at on sessions + notes to match
                # the staggered timestamps so the dashboard shows a real spread.
                for s in session_records:
                    if not s["session_id"] or not s["scheduled_at"]:
                        continue
                    ts = s["scheduled_at"].strftime("%Y-%m-%d %H:%M:%S+00")
                    cur.execute(
                        "UPDATE recording_sessions SET created_at = %s::timestamptz, "
                        "start_time = %s::timestamptz, end_time = (%s::timestamptz + INTERVAL '14 minutes') "
                        "WHERE id = %s",
                        (ts, ts, ts, str(s["session_id"])),
                    )
                    if s["note_id"]:
                        cur.execute(
                            "UPDATE soap_notes SET created_at = (%s::timestamptz + INTERVAL '15 minutes'), "
                            "updated_at = (%s::timestamptz + INTERVAL '20 minutes') "
                            "WHERE id = %s",
                            (ts, ts, str(s["note_id"])),
                        )

                cur.close()
                conn.close()
                did_db_tweaks = True
                print("  + DB tweaks applied")
            except Exception as exc:
                print(f"  ! DB tweak failed: {exc}")

# ────────────────────────────────────────────────────────────────────────────
# Step J — Audit traffic
# ────────────────────────────────────────────────────────────────────────────

print("\n[J] Seed extra audit traffic (varied GETs)")
all_tokens = list(phys_tokens.values()) + [admin_token]
note_ids_for_traffic = [s["note_id"] for s in session_records if s["note_id"]]
session_ids_for_traffic = [s["session_id"] for s in session_records if s["session_id"]]
patient_ids_for_traffic = [pid for pid in patient_ids if pid]
traffic_count = seed_audit_traffic(
    tokens=all_tokens,
    patient_ids=patient_ids_for_traffic,
    session_ids=session_ids_for_traffic,
    note_ids=note_ids_for_traffic,
    count=random.randint(28, 38),
)
print(f"  + {traffic_count} audit-log entries generated")

# ────────────────────────────────────────────────────────────────────────────
# Final summary
# ────────────────────────────────────────────────────────────────────────────

n_sessions = sum(1 for s in session_records if s["session_id"])
n_notes = sum(1 for s in session_records if s["note_id"])

print("\n=== Seed Complete ===")
print(f"Patients seeded:        {sum(1 for p in patient_ids if p)} / {len(PATIENTS)}")
print(f"Sessions created:       {n_sessions} / {N_SESSIONS}")
print(f"SOAP notes (DRAFT):     {n_notes}")
print(f"SOAP notes PATCHED:     {patched}")
print(f"SOAP notes APPROVED:    {approved}")
if did_db_tweaks:
    print(f"SOAP notes EXPIRED:     2")
    print(f"SOAP notes FHIR-pushed: 2")
print(f"Audit-log GETs:         {traffic_count}")
print()
print("--- Credentials ---")
print(f"Admin:      admin@clinnote-demo.com         / Admin@ClinNote2024!")
print(f"            (Admin: Alexandra Chen)")
print(f"Physician:  dr.jones@clinnote-demo.com      / Physician@Demo2024!   (Dr. Sarah Jones - Internal Medicine)")
print(f"Physician:  dr.patel@clinnote-demo.com      / Physician@Demo2024!   (Dr. Priya Patel - Cardiology)")
print(f"Physician:  dr.rodriguez@clinnote-demo.com  / Physician@Demo2024!   (Dr. Carlos Rodriguez - Family Medicine)")
print(f"Physician:  dr.wilson@clinnote-demo.com     / Physician@Demo2024!   (Dr. Jessica Wilson - Family Medicine)")
print(f"Physician:  dr.webb@clinnote-demo.com       / Physician@Demo2024!   (Dr. Marcus Webb - Emergency Medicine)")
print(f"Physician:  dr.tanaka@clinnote-demo.com     / Physician@Demo2024!   (Dr. Yuki Tanaka - Psychiatry)")
print(f"Nurse:      nurse.smith@clinnote-demo.com   / Nurse@Demo2024!       (Michael Smith)")
print()
print("Clinical templates used:")
for t in NOTE_CONTENTS:
    print(f"  * {t['label']:35s} ({t['specialty']})")
