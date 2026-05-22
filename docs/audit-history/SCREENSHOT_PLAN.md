# ClinNote AI — Complete Screenshot Plan

> Every feature must have a screenshot. This checklist tracks all frontend features, API surfaces, and edge cases.

---

## Pre-requisites
- [x] Fix BUG-008: backend `GET /notes/{id}` now returns structured `sections` object
- [x] Fix notes list shape: `list_notes` now returns `PaginatedResponse` format
- [x] Fix admin API routes: added `/admin/stats` and `/admin/sessions/active`
- [x] Verify Docker stack is fully up (all 7 services healthy)
- [x] Run seed script to populate demo data
- [x] Verify tokens load correctly via sessionStorage injection (with user role)

---

## Auth Pages

- [ ] **01-login-blank** — Login page, empty fields, HIPAA notice visible
- [ ] **02-login-filled** — Login page with email + password filled in
- [ ] **03-login-error** — Login attempt with wrong password → error message
- [ ] **04-login-mfa** — MFA / TOTP prompt screen (if triggered)

---

## Dashboard (Physician view)

- [ ] **05-dashboard-physician-top** — Dashboard top: pending notes count, today's sessions
- [ ] **06-dashboard-physician-scrolled** — Dashboard scrolled: recent sessions list with data
- [ ] **07-dashboard-quick-start** — "Start New Session" button / quick start area
- [ ] **08-dashboard-clinical-tip** — Clinical AI tip or info card (if rendered)

---

## New Session — 5-Step Wizard

- [ ] **09-new-session-step1-patient** — Step 1: Patient Info (MRN field, encounter ID)
- [ ] **10-new-session-step1-filled** — Step 1 with patient MRN filled in (MRN-001001)
- [ ] **11-new-session-step2-lab** — Step 2: Lab Reports / document upload area
- [ ] **12-new-session-step3-consent** — Step 3: Consent (verbal consent checkbox / modal)
- [ ] **13-new-session-step4-recording** — Step 4: Recording interface (mic button, timer)
- [ ] **14-new-session-step4-recording-active** — Step 4 recording in RECORDING state (pulsing)
- [ ] **15-new-session-step5-processing** — Step 5: Processing / AI generation in progress

---

## Notes History

- [ ] **16-notes-history-all** — Notes History page, "All" filter selected, notes listed
- [ ] **17-notes-history-draft** — Notes filtered by "Draft" status
- [ ] **18-notes-history-approved** — Notes filtered by "Approved" status
- [ ] **19-notes-history-expired** — Notes filtered by "Expired" status
- [ ] **20-notes-history-search** — Search box filled with query text
- [ ] **21-notes-history-scrolled** — Notes list scrolled to see more entries

---

## Note Review / SOAP Editor

- [ ] **22-note-review-header** — Note review top: patient info, session date, status badge
- [ ] **23-note-review-subjective** — Subjective section expanded with AI-generated text
- [ ] **24-note-review-objective** — Objective section with clinical findings
- [ ] **25-note-review-assessment** — Assessment section with diagnoses
- [ ] **26-note-review-plan** — Plan section with treatment plan
- [ ] **27-note-review-icd10** — ICD-10 codes widget showing suggested codes
- [ ] **28-note-review-cpt** — CPT codes widget
- [ ] **29-note-review-approve-button** — Approve button visible at bottom
- [ ] **30-note-review-approved** — Note after approval (status badge changes to "Approved")
- [ ] **31-note-review-fhir-push** — FHIR push button / status indicator

---

## Admin Panel

- [ ] **32-admin-dashboard-tab** — Admin page, "Live Dashboard" tab: active sessions, stats
- [ ] **33-admin-audit-log-tab** — Admin page, "Audit Log" tab: recent audit entries
- [ ] **34-admin-users-list** — Admin users list showing all 4 demo accounts
- [ ] **35-admin-hipaa-notice** — HIPAA compliance notice in admin panel (if present)

---

## Mobile Responsive (390×844)

- [ ] **36-mobile-login** — Login page on mobile viewport
- [ ] **37-mobile-dashboard** — Dashboard on mobile (physician)
- [ ] **38-mobile-notes-history** — Notes History on mobile
- [ ] **39-mobile-new-session** — New Session page on mobile

---

## API / Documentation

- [ ] **40-api-health** — `GET /health` JSON response in browser
- [ ] **41-swagger-ui-top** — Swagger UI `/docs` top section
- [ ] **42-swagger-ui-auth** — Swagger UI auth section expanded
- [ ] **43-swagger-ui-recordings** — Swagger UI recordings section expanded
- [ ] **44-swagger-ui-notes** — Swagger UI notes section expanded
- [ ] **45-openapi-schema** — `/openapi.json` raw JSON schema

---

## Edge Cases / Error States

- [ ] **46-404-page** — Unknown route → 404 / Not Found page
- [ ] **47-access-denied** — Physician accessing admin-only page → Access Denied
- [ ] **48-session-timeout** — Session expiry message (if implemented in UI)
- [ ] **49-empty-notes** — Notes History with no notes (fresh physician account)

---

## Summary

Total screenshots taken: **41** (`project-audit/screenshots/`)

All backend bugs fixed (BUG-008, notes list pagination, admin routes).
All screenshots show real authenticated data with proper role-based access.
Script: `project-audit/take_screenshots_v2.py`
