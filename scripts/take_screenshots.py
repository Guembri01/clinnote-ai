#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClinNote AI -- Canonical Screenshot Capture
============================================
Runs headless Chromium against a fully-seeded local stack and writes a clean,
sequentially-numbered set of JPEGs to project-audit/screenshots/.

Prerequisites:
  1. Backend running:    docker compose up -d   (or  uvicorn app.main:app --port 8003)
  2. Frontend running:   npm run dev            (Vite on :3000)
  3. Seed loaded:        python project-audit/seed_demo.py
  4. Playwright:         pip install playwright && playwright install chromium

Usage:
  python project-audit/take_screenshots.py
"""
import json, sys, time, requests
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("pip install playwright && playwright install chromium")
    sys.exit(1)

BASE_API = "http://localhost:8003/api/v1"

# Detect which port the frontend is on (prefer 3000, fall back to 3001)
def _detect_ui_port() -> str:
    for port in (3000, 3001):
        try:
            r = requests.get(f"http://localhost:{port}/", timeout=2)
            if r.status_code in (200, 304):
                return f"http://localhost:{port}"
        except Exception:
            continue
    # Default — script will fail loudly later if frontend isn't actually running
    return "http://localhost:3001"

BASE_UI = _detect_ui_port()
print(f"Frontend detected at: {BASE_UI}")

# Repo root is parent of this script's directory; screenshots are committed under docs/
SHOTS_DIR = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
SHOTS_DIR.mkdir(parents=True, exist_ok=True)

counter = [0]

# ── helpers ──────────────────────────────────────────────────────────────────

def shot(page, name, wait_ms=900):
    counter[0] += 1
    n = f"{counter[0]:02d}"
    fname = SHOTS_DIR / f"{n}-{name}.jpg"
    time.sleep(wait_ms / 1000)
    page.screenshot(path=str(fname), type="jpeg", quality=85, full_page=False)
    kb = fname.stat().st_size // 1024
    print(f"  [{n}] {name}.jpg  ({kb} KB)")
    return str(fname)

def api(method, path, token=None, **kwargs):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = getattr(requests, method)(f"{BASE_API}{path}", headers=headers,
                                  timeout=10, **kwargs)
    return r

def login(email, password):
    r = api("post", "/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"Login failed: {r.text[:100]}"
    return r.json()["access_token"]

def get_me(token):
    r = api("get", "/users/me", token=token)
    u = r.json()
    return {"id": u["id"], "email": u["email"],
            "full_name": f"{u['first_name']} {u['last_name']}",
            "role": u["role"], "mfa_enabled": u.get("totp_enabled", False),
            "created_at": u.get("created_at", "")}

def inject(page, token, refresh="", user=None):
    uj = json.dumps(user) if user else "null"
    page.evaluate(f"""() => {{
        sessionStorage.setItem('clinnote_access_token', '{token}');
        sessionStorage.setItem('clinnote_refresh_token', '{refresh}');
        sessionStorage.setItem('clinnote-auth', JSON.stringify({{
            state: {{ user: {uj}, accessToken: '{token}',
                      isAuthenticated: true, tempToken: null, mfaRequired: false }},
            version: 0
        }}));
    }}""")

def _with_screenshot_param(url: str) -> str:
    """Append ?screenshot=1 (or &screenshot=1) so the SPA can flip into a clean
    deterministic state (devtools hidden, recording mocks active, etc.)."""
    if "screenshot=" in url:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}screenshot=1"

def go(page, url, token, user=None, wait="networkidle"):
    page.goto(BASE_UI + "/", wait_until="domcontentloaded")
    inject(page, token, user=user)
    page.goto(_with_screenshot_param(url), wait_until=wait)
    time.sleep(0.7)

def wait(page, sel, t=8000):
    # sel may be a comma-separated list of fallback selectors
    for s in [x.strip() for x in sel.split(",")]:
        try:
            page.wait_for_selector(s, timeout=t // max(1, len(sel.split(","))))
            return
        except PlaywrightTimeout:
            continue

# ── pre-flight ────────────────────────────────────────────────────────────────

print("=== ClinNote AI Screenshots v3 ===")

dr_tok   = login("dr.jones@clinnote-demo.com", "Physician@Demo2024!")
adm_tok  = login("admin@clinnote-demo.com",    "Admin@ClinNote2024!")
dr_user  = get_me(dr_tok)
adm_user = get_me(adm_tok)
print(f"  Physician : {dr_user['full_name']} ({dr_user['role']})")
print(f"  Admin     : {adm_user['full_name']} ({adm_user['role']})")

# Grab note IDs (note1=draft MRN-001003, note2=draft MRN-001002, note3=approved MRN-001001)
notes_resp = api("get", "/notes?page=1&page_size=10", token=dr_tok).json()
notes = notes_resp.get("data", notes_resp) if isinstance(notes_resp, dict) else notes_resp
note_draft_id    = next((n["id"] for n in notes if n["status"] == "draft"), None)
note_approved_id = next((n["id"] for n in notes if n["status"] == "approved"), None)
print(f"  Draft note   : {note_draft_id}")
print(f"  Approved note: {note_approved_id}")

# ── playwright ────────────────────────────────────────────────────────────────

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])

    # ── DESKTOP 1280×800 ─────────────────────────────────────────────────────
    ctx  = browser.new_context(viewport={"width": 1280, "height": 800})
    ctx.add_init_script(
        "window.__CLINNOTE_SCREENSHOT_MODE = true;"
        "try { document.documentElement.classList.add('screenshot-mode'); }"
        " catch (e) {}"
    )
    page = ctx.new_page()
    page.set_default_timeout(30000)

    # ─── 01 Login blank ───────────────────────────────────────────────────────
    print("\n--- Auth Pages ---")
    page.goto(_with_screenshot_param(f"{BASE_UI}/login"), wait_until="networkidle")
    shot(page, "login-blank")

    # ─── 02 Login filled correctly ───────────────────────────────────────────
    page.fill('input[type="email"]',    "dr.jones@clinnote-demo.com")
    page.fill('input[type="password"]', "Physician@Demo2024!")
    shot(page, "login-filled")

    # ─── 03 Login error ───────────────────────────────────────────────────────
    page.goto(_with_screenshot_param(f"{BASE_UI}/login"), wait_until="networkidle")
    page.fill('input[type="email"]',    "wrong@hospital.org")
    page.fill('input[type="password"]', "WrongPassword123!")
    page.click('button[type="submit"]')
    time.sleep(1.8)
    shot(page, "login-error")

    # ─── 04 Dashboard – physician top ────────────────────────────────────────
    print("\n--- Dashboard ---")
    go(page, f"{BASE_UI}/dashboard", dr_tok, dr_user)
    wait(page, "h1, main")
    time.sleep(1.0)
    shot(page, "dashboard-physician-top")

    # ─── 05 Dashboard – admin view (Admin nav link visible) ──────────────────
    go(page, f"{BASE_UI}/dashboard", adm_tok, adm_user)
    wait(page, "h1, main")
    time.sleep(1.0)
    shot(page, "dashboard-admin-view")

    # ─── 06-11 New Session Wizard ─────────────────────────────────────────────
    print("\n--- New Session Wizard ---")

    # Step 1 blank
    go(page, f"{BASE_UI}/sessions/new", dr_tok, dr_user)
    wait(page, 'input[name="first_name"]')
    shot(page, "wizard-step1-blank")

    # Step 1 filled — use existing patient MRN-001002 (FK constraint requires patient to exist)
    # unique encounter ID to avoid duplicate session conflict on re-runs
    unique_enc = f"AUDIT-{int(time.time())}"
    page.fill('input[name="first_name"]',    "Robert")
    page.fill('input[name="last_name"]',     "Johnson")
    page.fill('input[name="mrn"]',           "MRN-001002")
    page.fill('input[name="date_of_birth"]', "1965-03-22")
    page.fill('input[name="encounter_id"]',  unique_enc)
    page.fill('input[name="chief_complaint"]', "Chest pain and shortness of breath")
    shot(page, "wizard-step1-filled")

    # Submit form → Step 2 Lab Reports
    page.click('button[type="submit"]')
    wait(page, "text=Lab Reports")
    shot(page, "wizard-step2-lab-reports")

    # Continue to Consent → Consent modal opens
    page.click("text=Continue without uploads")
    wait(page, "[role='dialog'], text=Recording Consent, text=Patient Consents")
    time.sleep(0.5)
    shot(page, "wizard-step3-consent-modal")

    # Click "Patient Consents" → API creates fresh session → Step 4 recording interface
    try:
        page.click("text=Patient Consents", timeout=4000)
        time.sleep(3.0)
        shot(page, "wizard-step4-recording-interface")
    except Exception:
        shot(page, "wizard-step4-recording-interface")

    # ─── NEW: Recording mid-stream (waveform + active state) ─────────────────
    # We're now on Step 4. Drive the Zustand recordingStore directly via the
    # module's exported hook (Vite exposes ESM modules — we fetch the module
    # via dynamic import on the page and call getState().setStatus etc.).
    recording_active = False
    try:
        # Click the "Tap to Record" / "Start recording" button to set
        # hasStarted=true so the RecordingTimer + TranscriptPanel render.
        clicked = False
        for sel in [
            'button[aria-label="Start recording"]',
            'text=Tap to Record',
        ]:
            try:
                page.click(sel, timeout=2500)
                clicked = True
                break
            except PlaywrightTimeout:
                continue

        # Whether or not the click landed (it usually fails in headless because
        # getUserMedia rejects), inject the recording-store state directly so
        # the waveform + "Recording in Progress" banner render.
        page.evaluate("""
            async () => {
              try {
                const mod = await import('/src/store/recordingStore.ts');
                const s = mod.useRecordingStore.getState();
                s.setStatus('recording');
                s.setDuration(47);
                s.setAudioLevel(0.6);
                s.setWsConnected(true);
              } catch (e) { /* module path may differ in build mode */ }
            }
        """)
        time.sleep(1.2)

        # If status didn't stick (page re-renders may revert), try one more time
        page.evaluate("""
            async () => {
              try {
                const mod = await import('/src/store/recordingStore.ts');
                mod.useRecordingStore.setState({
                  status: 'recording', duration: 47, audioLevel: 0.6, wsConnected: true,
                });
              } catch (e) {}
            }
        """)
        time.sleep(0.6)

        # Verify the "Recording in progress" banner is now visible
        try:
            page.wait_for_selector("text=Recording in progress", timeout=2500)
            recording_active = True
        except PlaywrightTimeout:
            pass
    except Exception as e:
        print(f"  recording-mid-stream injection failed: {type(e).__name__}: {e}")

    if recording_active:
        shot(page, "recording-mid-stream")
    else:
        shot(page, "recording-ready")

    # ─── NEW: AI Generation Progress (NoteGenerationScreen) ──────────────────
    # NewSessionPage now honors ?step=5&screenshot=1 to jump straight to the
    # AI generation progress screen so it can be captured deterministically.
    page.goto(BASE_UI + "/", wait_until="domcontentloaded")
    inject(page, dr_tok, user=dr_user)
    page.goto(f"{BASE_UI}/sessions/new?step=5&screenshot=1", wait_until="networkidle")
    try:
        page.wait_for_selector("text=Generating Your Note", timeout=5000)
    except PlaywrightTimeout:
        pass
    time.sleep(0.8)
    shot(page, "ai-generation-progress")

    # ─── 12-16 Notes History ──────────────────────────────────────────────────
    print("\n--- Notes History ---")

    # All statuses (3 notes: 2 draft + 1 approved)
    go(page, f"{BASE_UI}/notes", dr_tok, dr_user)
    wait(page, "text=Notes History")
    shot(page, "notes-history-all-statuses")

    # Draft filter (2 draft notes)
    try:
        page.locator("button, [role='tab']").filter(has_text="Draft").first.click()
        time.sleep(0.8)
        shot(page, "notes-history-draft-filter")
    except Exception:
        shot(page, "notes-history-draft-filter")

    # Approved filter (1 approved note — Jane Doe / pneumonia)
    try:
        page.locator("button, [role='tab']").filter(has_text="Approved").first.click()
        time.sleep(0.8)
        shot(page, "notes-history-approved-filter")
    except Exception:
        shot(page, "notes-history-approved-filter")

    # Expired filter (empty state)
    try:
        page.locator("button, [role='tab']").filter(has_text="Expired").first.click()
        time.sleep(0.8)
        shot(page, "notes-history-expired-empty")
    except Exception:
        shot(page, "notes-history-expired-empty")

    # Search by "Rossi" (matches seeded patient Isabella Rossi)
    try:
        page.locator("button, [role='tab']").filter(has_text="All").first.click()
        time.sleep(0.5)
        page.locator('input[type="search"], input[placeholder*="earch"]').first.fill("Rossi")
        time.sleep(0.8)
        shot(page, "notes-history-search")
    except Exception:
        shot(page, "notes-history-search")

    # ── scroll helper: app uses main#main-content with overflow-y-auto ────────
    def scroll_main(pg, top):
        pg.evaluate(f"(el=>{{if(el)el.scrollTop={top}}})(document.getElementById('main-content'))")

    # ─── 16-18 Note Review — draft (3 distinct viewport positions) ────────────
    print("\n--- Note Review (draft) ---")

    if note_draft_id:
        go(page, f"{BASE_UI}/notes/{note_draft_id}/review", dr_tok, dr_user)
        wait(page, "text=Review Note, text=Subjective")
        time.sleep(0.8)

        # Top: header + Draft badge + Approve button + Subjective section
        scroll_main(page, 0)
        time.sleep(0.4)
        shot(page, "note-review-header-draft")

        # Mid: scroll to show Assessment + Plan sections
        scroll_main(page, 650)
        time.sleep(0.5)
        shot(page, "note-review-assessment-plan")

        # Bottom: ICD-10 + CPT codes widget
        scroll_main(page, 99999)
        time.sleep(0.8)
        shot(page, "note-review-icd10-cpt-codes")

    # ─── 19 Note Review — approved (Approved badge + Push to EHR button) ──────
    print("\n--- Note Review (approved) ---")

    if note_approved_id:
        go(page, f"{BASE_UI}/notes/{note_approved_id}/review", dr_tok, dr_user)
        wait(page, "text=Review Note")
        time.sleep(0.8)
        scroll_main(page, 0)
        time.sleep(0.4)
        shot(page, "note-review-approved-status")

    # ─── NEW: AI vs Edited Diff view ─────────────────────────────────────────
    # Use the draft note (not approved) because the diff toolbar is hidden in
    # readOnly mode (approved notes render the editor read-only). The draft
    # note shows the "Show AI vs. Edited Diff" toggle button.
    if note_draft_id:
        go(page, f"{BASE_UI}/notes/{note_draft_id}/review", dr_tok, dr_user)
        wait(page, "text=Show AI vs. Edited Diff, text=Show Diff, text=Subjective", t=10000)
        time.sleep(0.8)
        scroll_main(page, 0)
        time.sleep(0.4)
        try:
            page.click("text=Show AI vs. Edited Diff", timeout=3000)
            time.sleep(0.8)
        except Exception:
            try:
                page.click("text=Show Diff", timeout=2000)
                time.sleep(0.8)
            except Exception:
                pass
        # Scroll a touch so the toggled-on toolbar + first diff are in frame
        scroll_main(page, 120)
        time.sleep(0.4)
        shot(page, "ai-vs-edited-diff")

    # ─── NEW: ICD Reasoning Drawer (opened state) ────────────────────────────
    # Open the approved note (which has ICD codes), scroll to bottom, click
    # the first ICD code chip. The "Why?" button is the entire chip itself.
    if note_approved_id:
        go(page, f"{BASE_UI}/notes/{note_approved_id}/review", dr_tok, dr_user)
        wait(page, "text=Review Note", t=10000)
        time.sleep(0.8)
        scroll_main(page, 99999)
        time.sleep(0.8)
        opened = False
        for sel in [
            'button[aria-label^="Show AI reasoning for"]',
            'button[aria-label*="reasoning"]',
            'text=Why?',
        ]:
            try:
                page.locator(sel).first.click(timeout=3000)
                opened = True
                break
            except Exception:
                continue
        if opened:
            # Wait for the drawer slide-in to settle
            try:
                page.wait_for_selector('[aria-labelledby="icd-reason-title"]', timeout=3000)
            except PlaywrightTimeout:
                pass
            time.sleep(0.7)
        shot(page, "icd-reasoning-drawer")

    # ─── 20-22 Admin Panel ────────────────────────────────────────────────────
    print("\n--- Admin Panel ---")

    # Admin — Live Dashboard (stats + active sessions table — fits one viewport)
    go(page, f"{BASE_UI}/admin", adm_tok, adm_user)
    wait(page, "text=Administration, text=Today")
    time.sleep(0.8)
    shot(page, "admin-live-dashboard")

    # Admin — Audit Log tab: HIPAA notice + first entries
    try:
        page.locator("button, [role='tab']").filter(has_text="Audit Log").first.click()
        time.sleep(1.5)
        scroll_main(page, 0)
        time.sleep(0.4)
        shot(page, "admin-audit-log-top")
    except Exception:
        shot(page, "admin-audit-log-top")

    # Audit Log — scrolled to show deeper entries
    scroll_main(page, 600)
    time.sleep(0.5)
    shot(page, "admin-audit-log-entries")

    # ─── NEW: Admin Users tab ────────────────────────────────────────────────
    try:
        # Click the Users tab by id (most reliable) — fall back to text
        clicked = False
        for sel in ['#tab-users', 'button[role="tab"]:has-text("Users")', 'text=Users']:
            try:
                page.locator(sel).first.click(timeout=2500)
                clicked = True
                break
            except Exception:
                continue
        if clicked:
            # Wait for the users table to render (at least one row)
            try:
                page.wait_for_selector('table tbody tr', timeout=8000)
            except PlaywrightTimeout:
                pass
            time.sleep(0.6)
            scroll_main(page, 0)
            time.sleep(0.3)
    except Exception:
        pass
    shot(page, "admin-users-tab")

    # ─── Edge cases: 404 + Access-denied ──────────────────────────────────────
    print("\n--- Edge Cases ---")

    # 404 — non-existent route while authenticated as physician
    go(page, f"{BASE_UI}/this-route-does-not-exist-1234", dr_tok, dr_user)
    time.sleep(1.0)
    shot(page, "edge-404-not-found")

    # Access-denied — physician (non-admin) trying to load /admin
    go(page, f"{BASE_UI}/admin", dr_tok, dr_user)
    time.sleep(1.2)
    shot(page, "edge-access-denied-admin")

    # ─── API surface: Swagger UI + /health ────────────────────────────────────
    print("\n--- API Surface ---")

    # Backend /docs (Swagger UI)
    page.goto("http://127.0.0.1:8003/docs", wait_until="networkidle")
    time.sleep(1.5)
    shot(page, "api-swagger-ui")

    # Backend /health (raw JSON)
    page.goto("http://127.0.0.1:8003/health", wait_until="networkidle")
    time.sleep(0.5)
    shot(page, "api-health-endpoint")

    # ─── NEW: MFA Setup page (disabled + enabled states) ─────────────────────
    print("\n--- MFA Setup ---")

    # Disabled state — initial CTA
    go(page, f"{BASE_UI}/settings/mfa", dr_tok, dr_user)
    wait(page, "text=Two-Factor Authentication, text=Enable MFA", t=10000)
    time.sleep(0.6)
    shot(page, "mfa-setup-disabled")

    # Setup state — let the real backend /auth/mfa/setup populate the page so
    # the otpauth URL + secret are real values. The frontend MfaSetupPage reads
    # setupData.otpauth_url and setupData.secret directly from the backend's
    # TOTPSetupResponse, so no mock is needed.
    try:
        page.click("text=Enable MFA", timeout=4000)
        # Wait for either of the setup-state headings
        try:
            page.wait_for_selector("text=Add to your authenticator, text=Confirm with a 6-digit code", timeout=5000)
        except PlaywrightTimeout:
            pass
        time.sleep(0.8)
    except Exception as e:
        print(f"  mfa-setup-enabled click failed: {type(e).__name__}: {e}")
    shot(page, "mfa-setup-enabled")

    # ─── NEW: MFA login challenge ────────────────────────────────────────────
    # 1. Enable real MFA on dr.jones via the backend API
    # 2. Log out (clear sessionStorage) and navigate to /login
    # 3. Fill creds + submit — frontend should toggle to the MFA challenge UI
    # 4. Capture screenshot
    # 5. Disable MFA so subsequent re-runs are idempotent
    print("\n--- MFA Login Challenge ---")

    mfa_enabled_on_dr = False
    try:
        r = api("post", "/auth/mfa/setup", token=dr_tok)
        if r.status_code == 200:
            mfa_enabled_on_dr = True
            print(f"  MFA enabled on dr.jones (secret hidden, len={len(r.json().get('secret',''))})")
        else:
            print(f"  /auth/mfa/setup → {r.status_code} {r.text[:120]}")
    except Exception as e:
        print(f"  /auth/mfa/setup failed: {e}")

    # Navigate fresh to /login (clear any cached sessionStorage)
    page.goto(_with_screenshot_param(f"{BASE_UI}/login"), wait_until="networkidle")
    page.evaluate("() => { sessionStorage.clear(); localStorage.clear(); }")
    page.goto(_with_screenshot_param(f"{BASE_UI}/login"), wait_until="networkidle")
    time.sleep(0.4)

    page.fill('input[type="email"]',    "dr.jones@clinnote-demo.com")
    page.fill('input[type="password"]', "Physician@Demo2024!")
    page.click('button[type="submit"]')

    # Two outcomes:
    # (a) frontend respects MFA → shows "Two-Factor Authentication" heading
    # (b) backend/frontend field mismatch (requires_mfa vs mfa_required) →
    #     login submit silently fails → stuck on credentials form
    captured_mfa_challenge = False
    try:
        page.wait_for_selector("text=Enter the code from your authenticator app", timeout=4500)
        captured_mfa_challenge = True
    except PlaywrightTimeout:
        pass

    time.sleep(0.6)
    if captured_mfa_challenge:
        # Defensive: clear any value the browser may have auto-filled into the
        # one-time-code input (some browsers reuse the password manager value).
        try:
            page.evaluate(
                "document.querySelectorAll('input[name=\"code\"], input[autocomplete=\"one-time-code\"]')"
                ".forEach(i => { i.value = ''; });"
            )
            time.sleep(0.3)
        except Exception:
            pass
        shot(page, "mfa-challenge")
    else:
        # Capture whatever the login page shows — typically still the
        # credentials form because of field-name mismatch.
        shot(page, "mfa-pending")
        print("  Frontend did not render the MFA challenge UI — captured login state as mfa-pending.jpg")

    # ─── Cleanup: disable MFA so dr.jones stays usable for re-runs ───────────
    # Re-login via API ignoring the challenge — backend issues a pending token
    # but we still need a *full* access token to call DELETE /auth/mfa/setup.
    # The dr_tok we already have is a fully scoped token from earlier (issued
    # before MFA was enabled) and remains valid until its 15-min TTL expires.
    if mfa_enabled_on_dr:
        try:
            r = api("delete", "/auth/mfa/setup", token=dr_tok)
            print(f"  MFA disable: {r.status_code}")
        except Exception as e:
            print(f"  MFA disable failed: {e}")

    # ── MOBILE 390×844 ───────────────────────────────────────────────────────
    print("\n--- Mobile (390×844) ---")

    mctx  = browser.new_context(viewport={"width": 390, "height": 844})
    mctx.add_init_script(
        "document.documentElement.classList.add('screenshot-mode');"
        " window.__CLINNOTE_SCREENSHOT_MODE = true;"
    )
    mpage = mctx.new_page()
    mpage.set_default_timeout(15000)

    mpage.goto(_with_screenshot_param(f"{BASE_UI}/login"), wait_until="networkidle")
    shot(mpage, "mobile-login")

    mpage.goto(BASE_UI + "/", wait_until="domcontentloaded")
    inject(mpage, dr_tok, user=dr_user)
    mpage.goto(_with_screenshot_param(f"{BASE_UI}/dashboard"), wait_until="networkidle")
    wait(mpage, "h1, main")
    shot(mpage, "mobile-dashboard")

    mpage.goto(_with_screenshot_param(f"{BASE_UI}/notes"), wait_until="networkidle")
    time.sleep(0.8)
    shot(mpage, "mobile-notes-history")

    mpage.goto(_with_screenshot_param(f"{BASE_UI}/sessions/new"), wait_until="networkidle")
    wait(mpage, 'input[name="first_name"]')
    shot(mpage, "mobile-new-session-wizard")

    if note_draft_id:
        mpage.goto(_with_screenshot_param(f"{BASE_UI}/notes/{note_draft_id}/review"), wait_until="networkidle")
        wait(mpage, "text=Review Note, text=Subjective")
        time.sleep(0.8)
        shot(mpage, "mobile-note-review")

    mctx.close()

    # ── Final: approved note bottom — ICD codes + FHIR push button ──────────
    print("\n--- Final Views ---")
    if note_approved_id:
        go(page, f"{BASE_UI}/notes/{note_approved_id}/review", dr_tok, dr_user)
        wait(page, "text=Review Note")
        time.sleep(0.8)
        scroll_main(page, 99999)
        time.sleep(0.6)
        shot(page, "note-approved-fhir-push-bottom")

    browser.close()

# ── summary ───────────────────────────────────────────────────────────────────
all_shots = sorted(SHOTS_DIR.glob("*.jpg"))
total_kb  = sum(f.stat().st_size for f in all_shots) // 1024
print(f"\n=== Done: {len(all_shots)} screenshots, {total_kb} KB ===")
for f in all_shots:
    print(f"  {f.name}  ({f.stat().st_size//1024} KB)")
