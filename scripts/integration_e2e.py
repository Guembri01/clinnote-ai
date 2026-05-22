"""
ClinNote AI - End-to-end Integration Test
==========================================
Drives the 14-step physician happy path against the running backend on :8003.
Exits 0 if all steps pass, non-zero otherwise.

Requires: requests (already installed in backend venv).
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from typing import Any

import requests

API = "http://127.0.0.1:8003"
ORIGIN = "http://localhost:3000"
STRONG_PW = "IntegrationTest@2026!Demo"  # 24 chars, upper, lower, digit, special

# Generate unique suffix so script can run multiple times against the same DB
SUFFIX = uuid.uuid4().hex[:8]

ADMIN_EMAIL = f"admin-e2e-{SUFFIX}@example.com"
PHYSICIAN_EMAIL = f"physician-e2e-{SUFFIX}@example.com"
PATIENT_MRN = f"MRN-E2E-{SUFFIX.upper()}"

results: list[tuple[int, bool, str]] = []


def record(step: int, ok: bool, msg: str) -> None:
    status = "PASS" if ok else "FAIL"
    print(f"[step {step}] {status} - {msg}")
    results.append((step, ok, msg))


def short(body: Any, n: int = 200) -> str:
    try:
        return json.dumps(body)[:n]
    except Exception:
        return str(body)[:n]


def login_with_retry(session: requests.Session, email: str, password: str, label: str) -> requests.Response:
    """POST /auth/login with up to 6x retry on 429 (rate-limited)."""
    for attempt in range(6):
        r = session.post(
            f"{API}/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        if r.status_code == 429:
            print(f"    [{label}] rate-limited (HTTP 429), backing off 65s (attempt {attempt + 1}/6)")
            time.sleep(65)
            continue
        return r
    return r  # type: ignore[return-value]


def main() -> int:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "Accept": "application/json"})

    # --- Step 1: Bootstrap admin (or 403 if one exists) ---
    r = s.post(
        f"{API}/api/v1/auth/bootstrap",
        json={
            "email": ADMIN_EMAIL,
            "password": STRONG_PW,
            "first_name": "Admin",
            "last_name": "E2E",
            "role": "admin",
        },
    )
    bootstrap_used_existing = False
    if r.status_code == 201:
        record(1, True, f"got HTTP 201, body: {short(r.json())}")
    elif r.status_code == 403:
        # Admin already exists in DB - we need a working admin we can log in as.
        # The spec says "201 or 403 already exists" is acceptable. Mark pass.
        # We'll log in with the admin we provisioned in this run if 201 happened
        # in a prior probe, otherwise we can't proceed without known credentials.
        bootstrap_used_existing = True
        record(1, True, f"got HTTP 403 (admin exists - already bootstrapped), body: {short(r.json())}")
    else:
        record(1, False, f"got HTTP {r.status_code}, body: {short(r.text)}")
        return 1

    # --- Step 2: Login as admin ---
    if bootstrap_used_existing:
        # We can't log in without known credentials. Try a sentinel admin known
        # to exist (the one from the probe inside the integration runner).
        for trial_email, trial_pw in [
            (ADMIN_EMAIL, STRONG_PW),
            ("probe-doesnt-matter@test.com", "AAAAaaaa1111@@@@"),
        ]:
            r = login_with_retry(s, trial_email, trial_pw, "admin-login")
            if r.status_code == 200:
                break
        else:
            record(2, False, f"could not log in with any known admin; last HTTP {r.status_code}")
            return 1
    else:
        r = login_with_retry(s, ADMIN_EMAIL, STRONG_PW, "admin-login")

    if r.status_code != 200:
        record(2, False, f"got HTTP {r.status_code}, body: {short(r.text)}")
        return 1
    admin_tok = r.json().get("access_token")
    if not admin_tok:
        record(2, False, f"no access_token in body: {short(r.json())}")
        return 1
    record(2, True, f"got HTTP 200, access_token len={len(admin_tok)}")

    admin_headers = {"Authorization": f"Bearer {admin_tok}"}

    # --- Step 3: Register physician (admin-only) ---
    r = s.post(
        f"{API}/api/v1/auth/register",
        headers=admin_headers,
        json={
            "email": PHYSICIAN_EMAIL,
            "password": STRONG_PW,
            "first_name": "Phys",
            "last_name": "E2E",
            "role": "physician",
            "specialty": "primary_care",
        },
    )
    if r.status_code != 201:
        record(3, False, f"got HTTP {r.status_code}, body: {short(r.text)}")
        return 1
    record(3, True, f"got HTTP 201, body: {short(r.json())}")

    # --- Step 4: Login as physician ---
    r = login_with_retry(s, PHYSICIAN_EMAIL, STRONG_PW, "physician-login")
    if r.status_code != 200:
        record(4, False, f"got HTTP {r.status_code}, body: {short(r.text)}")
        return 1
    phys_tok = r.json().get("access_token")
    if not phys_tok:
        record(4, False, f"no access_token: {short(r.json())}")
        return 1
    record(4, True, f"got HTTP 200, access_token len={len(phys_tok)}")
    phys_headers = {"Authorization": f"Bearer {phys_tok}"}

    # --- Step 5: Create patient ---
    r = s.post(
        f"{API}/api/v1/patients",
        headers=phys_headers,
        json={
            "mrn": PATIENT_MRN,
            "first_name": "Jane",
            "last_name": "Doe",
            "dob": "1985-03-22",
            "encounter_id": f"ENC-{SUFFIX}",
        },
    )
    if r.status_code != 201:
        record(5, False, f"got HTTP {r.status_code}, body: {short(r.text)}")
        return 1
    record(5, True, f"got HTTP 201, body: {short(r.json())}")

    # --- Step 6: Start recording ---
    r = s.post(
        f"{API}/api/v1/recordings/start",
        headers=phys_headers,
        json={
            "patient_mrn": PATIENT_MRN,
            "encounter_id": f"ENC-{SUFFIX}",
            "session_metadata": {"room": "Exam-1", "specialty": "primary_care"},
        },
    )
    if r.status_code != 201:
        record(6, False, f"got HTTP {r.status_code}, body: {short(r.text)}")
        return 1
    session_obj = r.json()
    session_id = session_obj.get("id")
    record(6, True, f"got HTTP 201, session_id={session_id}, status={session_obj.get('status')}")

    # --- Step 7: Record consent ---
    r = s.post(
        f"{API}/api/v1/consent/record",
        headers=phys_headers,
        json={
            "session_id": session_id,
            "consent_type": "verbal",
            "notes": "Patient verbally confirmed",
        },
    )
    if r.status_code not in (200, 201):
        record(7, False, f"got HTTP {r.status_code}, body: {short(r.text)}")
        return 1
    record(7, True, f"got HTTP {r.status_code}, body: {short(r.json())}")

    # --- Step 8: Stop recording (creates stub SOAP note) ---
    r = s.post(
        f"{API}/api/v1/recordings/{session_id}/stop",
        headers=phys_headers,
    )
    if r.status_code != 200:
        record(8, False, f"got HTTP {r.status_code}, body: {short(r.text)}")
        return 1
    stop_body = r.json()
    note_id = stop_body.get("note_id")
    record(8, True, f"got HTTP 200, note_id={note_id}")

    # --- Step 9: GET /notes - list ---
    r = s.get(f"{API}/api/v1/notes", headers=phys_headers)
    if r.status_code != 200:
        record(9, False, f"got HTTP {r.status_code}, body: {short(r.text)}")
        return 1
    notes_body = r.json()
    notes_count = len(notes_body.get("data", [])) if isinstance(notes_body, dict) else len(notes_body)
    record(9, True, f"got HTTP 200, notes count={notes_count}")

    if not note_id:
        # Fallback: pick first note belonging to physician
        if isinstance(notes_body, dict) and notes_body.get("data"):
            note_id = notes_body["data"][0]["id"]
        else:
            record(9, False, f"no note_id available; body: {short(notes_body)}")
            return 1

    # --- Step 10: PATCH note with realistic SOAP content ---
    r = s.patch(
        f"{API}/api/v1/notes/{note_id}",
        headers=phys_headers,
        json={
            "subjective": "45-year-old patient presents with 3 days of sore throat and low-grade fever. Denies cough or shortness of breath.",
            "objective": "Vitals: Temp 38.1C, BP 122/78, HR 84, RR 16, SpO2 98%. Oropharynx erythematous with bilateral tonsillar exudate. No cervical lymphadenopathy. Lungs clear bilaterally.",
            "assessment": "1. Acute pharyngitis (J02.9), likely viral but cannot rule out streptococcal infection.\n2. Rule out group A strep pharyngitis.",
            "plan": "1. Rapid strep antigen test in-clinic.\n2. Symptomatic care: acetaminophen 500mg PO q6h PRN, warm salt-water gargles.\n3. Return if fever >39C, difficulty swallowing, or symptoms persist >5 days.",
            "icd_codes": [{"code": "J02.9", "description": "Acute pharyngitis, unspecified", "confidence": 0.92, "is_primary": True}],
            "cpt_codes": [{"code": "99213", "description": "Office visit, established patient, low complexity", "confidence": 0.88}],
        },
    )
    if r.status_code != 200:
        record(10, False, f"got HTTP {r.status_code}, body: {short(r.text)}")
        return 1
    record(10, True, f"got HTTP 200, status={r.json().get('status')}")

    # --- Step 11: Approve note (physician) ---
    r = s.post(
        f"{API}/api/v1/notes/{note_id}/approve",
        headers=phys_headers,
        json={"attestation": "I attest that this note accurately reflects the clinical encounter."},
    )
    if r.status_code != 200:
        record(11, False, f"got HTTP {r.status_code}, body: {short(r.text)}")
        return 1
    record(11, True, f"got HTTP 200, status={r.json().get('status')}")

    # --- Step 12: GET note - verify approved status ---
    r = s.get(f"{API}/api/v1/notes/{note_id}", headers=phys_headers)
    if r.status_code != 200:
        record(12, False, f"got HTTP {r.status_code}, body: {short(r.text)}")
        return 1
    note_final = r.json()
    if note_final.get("status") != "approved":
        record(12, False, f"got HTTP 200, but status='{note_final.get('status')}' (expected 'approved')")
        return 1
    record(12, True, f"got HTTP 200, status='approved'")

    # --- Step 13: GET admin audit log ---
    r = s.get(f"{API}/api/v1/admin/audit-log?days_back=1", headers=admin_headers)
    if r.status_code != 200:
        record(13, False, f"got HTTP {r.status_code}, body: {short(r.text)}")
        return 1
    audit_body = r.json()
    entries = audit_body.get("data", []) if isinstance(audit_body, dict) else audit_body
    # Audit log returns action enum names in uppercase (e.g. "LOGIN", "CREATE_PATIENT")
    actions = {(e.get("action") or "").upper() for e in entries}
    expected = {"LOGIN", "CREATE_PATIENT", "APPROVE_NOTE"}
    missing = expected - actions
    if missing:
        record(13, False, f"got HTTP 200 but missing actions {missing}; observed={sorted(actions)[:15]}")
        return 1
    record(13, True, f"got HTTP 200, {len(entries)} entries; contains {sorted(expected)}")

    # --- Step 14: CORS preflight ---
    r = requests.options(
        f"{API}/api/v1/users/me",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    if r.status_code not in (200, 204):
        record(14, False, f"got HTTP {r.status_code}, headers: {dict(r.headers)}")
        return 1
    allow_origin = r.headers.get("access-control-allow-origin", "")
    if allow_origin not in (ORIGIN, "*"):
        record(14, False, f"got HTTP {r.status_code} but Access-Control-Allow-Origin='{allow_origin}' (expected {ORIGIN})")
        return 1
    record(14, True, f"got HTTP {r.status_code}, Access-Control-Allow-Origin='{allow_origin}'")

    return 0


if __name__ == "__main__":
    rc = main()
    passes = sum(1 for _, ok, _ in results if ok)
    fails = sum(1 for _, ok, _ in results if not ok)
    print()
    print(f"SUMMARY: {passes} passed, {fails} failed (of {len(results)} run)")
    sys.exit(rc)
