"""
ClinNote AI — API Smoke Test
=============================
Hits a curated matrix of public + authenticated endpoints against a running
backend (assumed on http://127.0.0.1:8003) and prints a Markdown results
table. Exit code 0 if every row passes, 1 otherwise.

Usage:
    backend\\.venv\\Scripts\\python.exe project-audit\\smoke_endpoints.py
"""

from __future__ import annotations

import sys
import time
import uuid
from typing import Any, Iterable

import requests


BASE = "http://127.0.0.1:8003"
API = f"{BASE}/api/v1"
ADMIN_EMAIL = f"smoke-admin-{uuid.uuid4().hex[:8]}@clinnote.example.com"
ADMIN_PASSWORD = "Demo@ClinNote2024!"
# Use a syntactically valid email so the rate limiter runs AFTER body parsing.
BOGUS_LOGIN = {"email": "nobody@clinnote.example.com", "password": "wrongpass!"}


Row = dict[str, Any]
rows: list[Row] = []


def record(
    method: str,
    path: str,
    expected: Iterable[int],
    actual: int,
    note: str = "",
) -> bool:
    expected_set = set(expected)
    ok = actual in expected_set
    rows.append(
        {
            "method": method,
            "path": path,
            "expected": "/".join(str(s) for s in sorted(expected_set)),
            "actual": actual,
            "ok": ok,
            "note": note,
        }
    )
    return ok


def safe_status(resp: requests.Response | None) -> int:
    if resp is None:
        return 0
    return resp.status_code


def call(method: str, url: str, **kwargs) -> requests.Response | None:
    try:
        return requests.request(method, url, timeout=15, **kwargs)
    except requests.RequestException as exc:
        print(f"[error] {method} {url} -> {exc}", file=sys.stderr)
        return None


# --------------------------------------------------------------------------- #
# Stage A — unauthenticated
# --------------------------------------------------------------------------- #
def stage_unauth() -> None:
    r = call("GET", f"{BASE}/health")
    record("GET", "/health", [200], safe_status(r))

    r = call("GET", f"{BASE}/docs")
    record("GET", "/docs", [200], safe_status(r))

    r = call("GET", f"{BASE}/openapi.json")
    record("GET", "/openapi.json", [200], safe_status(r))

    r = call("POST", f"{API}/auth/login", json={"foo": "bar"})
    record("POST", "/auth/login (bogus body)", [401, 422], safe_status(r))

    # Rate-limit check: hammer login 6× with same IP
    final_status = 0
    for i in range(6):
        r = call("POST", f"{API}/auth/login", json=BOGUS_LOGIN)
        final_status = safe_status(r)
    record(
        "POST x6",
        "/auth/login (rate limit)",
        [429],
        final_status,
        note="final call after 6 rapid attempts",
    )

    r = call("GET", f"{API}/patients")
    record("GET", "/patients (no token)", [401, 403], safe_status(r))

    r = call("GET", f"{API}/notes")
    record("GET", "/notes (no token)", [401, 403], safe_status(r))

    r = call("GET", f"{API}/admin/audit-log")
    record("GET", "/admin/audit-log (no token)", [401, 403], safe_status(r))


# --------------------------------------------------------------------------- #
# Stage B — bootstrap + auth
# --------------------------------------------------------------------------- #
def stage_bootstrap_and_login() -> str | None:
    """Returns access_token (or None on failure)."""
    bootstrap_body = {
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
        "first_name": "Smoke",
        "last_name": "Admin",
        "role": "admin",
    }
    r = call("POST", f"{API}/auth/bootstrap", json=bootstrap_body)
    status = safe_status(r)
    record("POST", "/auth/bootstrap", [201, 403], status)

    login_email = ADMIN_EMAIL
    login_pwd = ADMIN_PASSWORD
    # If bootstrap already taken, fall back to seeding via /auth/login w/ known
    # demo-seed admin (project-audit/seed_demo.py uses alexandra.chen@clinnote.ai).
    if status == 403:
        login_email = "alexandra.chen@clinnote.ai"
        login_pwd = "Demo@ClinNote2024!"

    # Wait briefly so login rate limit window expires
    time.sleep(62)

    r = call(
        "POST",
        f"{API}/auth/login",
        json={"email": login_email, "password": login_pwd},
    )
    status = safe_status(r)
    record("POST", "/auth/login (valid creds)", [200], status)
    if status != 200 or r is None:
        return None
    try:
        return r.json().get("access_token")
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Stage C — authenticated matrix
# --------------------------------------------------------------------------- #
def stage_auth(token: str) -> None:
    h = {"Authorization": f"Bearer {token}"}

    r = call("GET", f"{API}/users/me", headers=h)
    record("GET", "/users/me", [200], safe_status(r))

    r = call("GET", f"{API}/users", headers=h)
    record("GET", "/users", [200], safe_status(r))

    # Create a fresh patient
    mrn = f"SMOKE-{uuid.uuid4().hex[:8].upper()}"
    pat_body = {
        "mrn": mrn,
        "first_name": "Smoke",
        "last_name": "Test",
        "dob": "1990-01-01",
        "encounter_id": f"ENC-{uuid.uuid4().hex[:6]}",
    }
    r = call("POST", f"{API}/patients", headers=h, json=pat_body)
    record("POST", "/patients", [201], safe_status(r))

    r = call("GET", f"{API}/patients", headers=h)
    record("GET", "/patients", [200], safe_status(r))

    # Start recording session
    r = call(
        "POST",
        f"{API}/recordings/start",
        headers=h,
        json={"patient_mrn": mrn, "encounter_id": pat_body["encounter_id"]},
    )
    status = safe_status(r)
    record("POST", "/recordings/start", [201], status)
    session_id: str | None = None
    if r is not None and status == 201:
        try:
            session_id = r.json().get("id")
        except Exception:
            session_id = None

    # Record consent
    if session_id:
        r = call(
            "POST",
            f"{API}/consent/record",
            headers=h,
            json={"session_id": session_id, "consent_type": "verbal", "notes": "smoke"},
        )
        record("POST", "/consent/record", [200, 201], safe_status(r))

        r = call("POST", f"{API}/recordings/{session_id}/stop", headers=h)
        record("POST", "/recordings/{id}/stop", [200], safe_status(r))
    else:
        record("POST", "/consent/record", [200, 201], 0, note="skipped: no session_id")
        record("POST", "/recordings/{id}/stop", [200], 0, note="skipped: no session_id")

    r = call("GET", f"{API}/notes", headers=h)
    record("GET", "/notes", [200], safe_status(r))

    r = call("GET", f"{API}/icd/search?q=diabetes", headers=h)
    record("GET", "/icd/search?q=diabetes", [200], safe_status(r))

    r = call("GET", f"{API}/admin/audit-log", headers=h)
    record("GET", "/admin/audit-log", [200], safe_status(r))

    r = call("GET", f"{API}/admin/stats", headers=h)
    record("GET", "/admin/stats", [200], safe_status(r))


# --------------------------------------------------------------------------- #
# Pretty-print
# --------------------------------------------------------------------------- #
def print_markdown_table() -> None:
    print()
    print("| # | Method | Path | Expected | Actual | OK | Note |")
    print("|---|--------|------|---------:|-------:|----|------|")
    for i, row in enumerate(rows, 1):
        ok = "PASS" if row["ok"] else "FAIL"
        print(
            f"| {i} | {row['method']} | `{row['path']}` "
            f"| {row['expected']} | {row['actual']} | {ok} | {row['note']} |"
        )
    print()


def main() -> int:
    print(f"[smoke] target = {BASE}")
    stage_unauth()
    token = stage_bootstrap_and_login()
    if token:
        stage_auth(token)
    else:
        print("[smoke] ERROR: could not obtain access token; skipping authed stage")

    print_markdown_table()
    failures = [r for r in rows if not r["ok"]]
    print(f"[smoke] {len(rows) - len(failures)} pass / {len(failures)} fail")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
