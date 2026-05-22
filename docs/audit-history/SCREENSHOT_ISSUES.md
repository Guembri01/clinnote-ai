# ClinNote AI — Screenshot Issues Report

> Full audit of all 32 screenshots. Every bug listed with root cause and fix status.

---

## Bug #1 — Screenshot 10: "Error: Failed to start session" banner visible
**File:** `10-wizard-step4-recording-interface.jpg`  
**What's wrong:** Step 4 (Recording Interface) shows a red error banner "Failed to start session" and never advances past Step 2 (Lab Reports).  
**Root cause:** Two issues combined: (a) `startRecording()` in `frontend/src/api/recordings.ts` sent `{patient, consent, lab_document_ids}` but the backend expects `{patient_mrn, encounter_id, session_metadata}`; (b) script used MRN-009001 which violates the FK constraint `recording_sessions_patient_mrn_fkey` since that patient doesn't exist.  
**Fix:** Updated `startRecording()` to transform the payload to backend format and map the response back to the frontend type. Changed script to use existing MRN-001002 (Robert Johnson) with unique encounter ID.  
- [x] Fixed

---

## Bug #2 — Screenshot 03: Raw API error "Request failed with status code 401"
**File:** `03-login-error.jpg`  
**What's wrong:** The error toast shows the raw Axios error string instead of a human-readable message.  
**Root cause:** Backend returns `{"detail": "Invalid credentials"}` (FastAPI default). `normalizeError()` in `client.ts` checks `data.message` first — which is `undefined` — then falls back to `error.message` = Axios's raw text.  
**Fix:** In `LoginPage.tsx`, map a 401 status explicitly to `"Invalid email or password. Please try again."` instead of relying on the generic fallback.  
- [x] Fixed

---

## Bug #3 — Screenshots 11–15: Patient names show "Clinical Patient" instead of real names
**Files:** `11` through `15` (all Notes History screenshots), also visible in Dashboard.  
**What's wrong:** Every note row shows `Clinical Patient ***1003` etc. instead of `Jane Doe`, `John Smith`, `Mary Johnson`.  
**Root cause:** `backend/app/api/v1/notes.py` line 140 hardcodes `"patient_name": "Clinical Patient"` — the actual patient name is never fetched or decrypted.  
**Fix:** Join the `Patient` table via `mrn_hmac` lookup for each note's MRN and decrypt `enc_first_name + enc_last_name`.  
- [x] Fixed

---

## Bug #4 — Screenshots 12, 13, 14: Filter tabs highlighted but list unchanged
**Files:** `12-notes-history-draft-filter.jpg`, `13-notes-history-approved-filter.jpg`, `14-notes-history-expired-empty.jpg`  
**What's wrong:** Clicking Draft/Approved/Expired highlights the tab but the list still shows all 3 notes regardless. The "Expired" filter should show an empty state.  
**Root cause:** `NotesHistoryPage.tsx` updates URL search params but `SessionList` receives only `limit` and `showPagination` props — it ignores `status` and `search` entirely. Its React Query key is `['notes-history', page, limit]` so it never re-fetches on filter change.  
**Fix:** Add `status` and `search` props to `SessionList`; include them in the query key and pass them to `getNotesHistory()`.  
- [x] Fixed

---

## Bug #5 — Screenshots 16–22: "Encounter:" field always empty in note review header
**Files:** All note review screenshots.  
**What's wrong:** The header reads `MRN: MRN-001003  Encounter:` with no value after the colon.  
**Root cause:** `SOAPNoteRead` schema has no `encounter_id` field, so `note.encounter_id` is always `undefined` in `ReviewNotePage.tsx`. The `_decrypt_note` function never populates it.  
**Fix:** Add `encounter_id: str | None = None` to `SOAPNoteRead`; in `_decrypt_note`, join `RecordingSession` and set it. Also add `patient_name: str | None = None` so the header shows the patient's name.  
- [x] Fixed

---

## Bug #6 — Screenshot 21: ICD-10/CPT codes section not visible
**File:** `21-note-review-icd10-cpt-codes.jpg`  
**What's wrong:** Shows the exact same view as screenshot 16 (Subjective section at the top) — the scroll never reached the ICD/CPT widget at the bottom.  
**Root cause:** `window.scrollTo(0, document.body.scrollHeight - 300)` in headless Chromium evaluates `scrollHeight` before the full page renders, yielding a value that's too small.  
**Fix:** Use `window.scrollTo(0, 99999)` (a value larger than any realistic page height) to guarantee the page scrolls to its absolute bottom.  
- [x] Fixed

---

## Bug #7 — Screenshots 25 & 26: Admin audit log screenshots are identical
**Files:** `25-admin-audit-log-hipaa-notice.jpg`, `26-admin-audit-log-entries.jpg`  
**What's wrong:** Both screenshots show exactly the same audit log table — scrolling 250px made no visible difference because the HIPAA notice + table headers together occupy less than 250px.  
**Fix:** Renamed screenshot 26 to `admin-audit-log-more-entries` and scrolled 500px instead to show deeper entries in the log.  
- [x] Fixed

---

## Bug #8 — Screenshot 03: Unprofessional test email "hacker@evil.com"
**File:** `03-login-error.jpg`  
**What's wrong:** Portfolio/demo screenshot uses `hacker@evil.com` — looks inappropriate for a professional clinical product demo.  
**Fix:** Changed to `wrong@hospital.org` with password `WrongPassword123!` in the script.  
- [x] Fixed

---

## Summary

| # | Screenshot | Problem | Fix Location | Status |
|---|-----------|---------|-------------|--------|
| 1 | 10 | "Failed to start session" error banner | `frontend/src/api/recordings.ts` + script MRN | ✅ Fixed |
| 2 | 03 | Raw "Request failed with status code 401" | `frontend/src/pages/LoginPage.tsx` | ✅ Fixed |
| 3 | 11–15 | "Clinical Patient" hardcoded patient name | `backend/app/api/v1/notes.py` list_notes | ✅ Fixed |
| 4 | 12–14 | Filter tabs don't filter the list | `frontend/src/components/organisms/SessionList.tsx` | ✅ Fixed |
| 5 | 16–22 | Empty "Encounter:" field in note review | `backend/app/schemas/soap_note.py` + notes.py | ✅ Fixed |
| 6 | 21 | ICD-10/CPT scroll doesn't reach bottom | Script scroll value | ✅ Fixed |
| 7 | 25–26 | Two identical audit log screenshots | Script screenshot name + scroll depth | ✅ Fixed |
| 8 | 03 | "hacker@evil.com" unprofessional email | Script test credentials | ✅ Fixed |

**All 8 bugs resolved. 32 screenshots generated clean.**
