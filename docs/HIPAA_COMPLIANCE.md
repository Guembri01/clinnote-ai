# HIPAA Compliance Posture — ClinNote AI

> This document is the engineering-side companion to a covered entity's HIPAA Risk Assessment and Business Associate Agreement (BAA). It is **not** legal advice.

## Role
ClinNote AI operates as a **Business Associate** to its customer covered entities (hospitals, clinics, group practices). A signed BAA between ClinNote AI and the customer is a prerequisite for any production PHI flow.

---

## Technical Safeguards — 45 CFR §164.312

| Control | Required by | Implementation |
|---|---|---|
| **§164.312(a)(1)** Access control | unique user IDs | `users.email` is the unique identifier; all PHI access tied to `user_id` in `audit_logs`. |
| **§164.312(a)(2)(i)** Unique user IDs | yes | UUID PK + unique email + optional NPI. |
| **§164.312(a)(2)(ii)** Emergency access | yes | Admin role can read all PHI; emergency-override consent flow documented in `frontend/src/components/molecules/ConsentModal.tsx`. |
| **§164.312(a)(2)(iii)** Automatic logoff | yes | `SessionTimeoutMiddleware` enforces 15-minute inactivity timeout (`SESSION_INACTIVITY_TIMEOUT=900`). |
| **§164.312(a)(2)(iv)** Encryption/decryption | required where reasonable | All PHI columns encrypted at rest with Fernet; in transit via TLS 1.3. See `app/utils/encryption.py`. |
| **§164.312(b)** Audit controls | yes | `audit_logs` table with PL/pgSQL `BEFORE UPDATE/DELETE` triggers that raise an error. All PHI access logged. |
| **§164.312(c)(1)** Integrity controls | yes | Fernet ciphertexts are MAC-protected (any tamper raises `InvalidToken`). |
| **§164.312(d)** Person/entity authentication | yes | JWT + bcrypt password (cost 12) + optional TOTP MFA. Account lockout after 5 failed attempts. |
| **§164.312(e)(1)** Transmission security | yes | TLS 1.3 enforced. WebSocket via WSS only. |
| **§164.312(e)(2)(i)** Integrity controls in transit | yes | TLS authenticated encryption. |
| **§164.312(e)(2)(ii)** Encryption in transit | yes | Mandatory at the LB; HSTS preload. |

## Administrative Safeguards — 45 CFR §164.308

| Control | Implementation |
|---|---|
| Security Management Process (§164.308(a)(1)) | Annual risk assessment; this document + `docs/THREAT_MODEL.md`. |
| Workforce Security (§164.308(a)(3)) | Role-based access in app; HR background check policy (out-of-repo). |
| Information Access Management (§164.308(a)(4)) | RBAC enforced server-side via `require_roles()` dependency. |
| Security Awareness and Training (§164.308(a)(5)) | Annual training; in-app HIPAA notices on consent + audit screens. |
| Security Incident Procedures (§164.308(a)(6)) | See `docs/INCIDENT_RESPONSE.md`. |
| Contingency Plan (§164.308(a)(7)) | Daily PG backups, 30-day retention, monthly restore drill. |
| Evaluation (§164.308(a)(8)) | Quarterly automated dependency audit + annual third-party pen test. |

## Physical Safeguards — 45 CFR §164.310
Implemented by the cloud host (AWS / GCP / Azure) per their HIPAA-eligible service documentation. No ClinNote AI–owned facility hosts PHI.

---

## Patient Consent

- Every recording session is **gated** by a recorded patient consent (verbal or written) — see `app/api/v1/consent.py`.
- Consent record stores `consent_recorded_at`, `consent_ip`, `consent_type`, free-text notes.
- Consent UI is available in **English, Spanish, French** in the frontend `ConsentModal`.
- Sessions cannot transition from `pending_consent` to `recording` without a consent record.

---

## Data Retention

See `docs/DATA_RETENTION.md` for the full schedule. Summary:

| Data | Retention | Mechanism |
|---|---|---|
| Audio recordings | ≤ 24 hours after note generation; deleted on note approval | Celery beat task `purge_stale_audio` (every 5 min); in-memory + Redis TTL |
| Unapproved SOAP notes (DRAFT) | 24 hours; auto-expire | `purge_expired_notes` beat task (every 15 min) |
| Approved SOAP notes | 7 years | Retained in `soap_notes` table; partitioned archive after 2 years |
| Audit logs | 6 years minimum (HIPAA §164.316) | Append-only, monthly partitioning (planned) |
| Transcripts | Linked to session; deleted with session | `ON DELETE CASCADE` from `recording_sessions` |

---

## Breach Notification

ClinNote AI follows the 60-day **HIPAA Breach Notification Rule** (45 CFR §164.404) and the 72-hour **GDPR Article 33** equivalent for EU customers.

| Severity | Notification window | Process |
|---|---|---|
| Confirmed PHI breach affecting ≥ 500 individuals | 60 days to HHS + media; immediate to customer | See `docs/INCIDENT_RESPONSE.md` |
| Confirmed PHI breach affecting < 500 individuals | Annual HHS log + customer notification | Same |
| Suspected breach under investigation | 72 hours preliminary notice to affected customers | Same |
| Non-PHI security event | Internal post-mortem only | Same |

---

## BAA Template

A reference BAA template is provided at `docs/legal/BAA_template.md` (to be added by Legal). Required fields:
- Permitted uses and disclosures of PHI by ClinNote AI.
- Safeguards (this document).
- Reporting obligations.
- Subcontractor flow-down (OpenAI, DeepInfra, Azure must each have their own BAA in place).
- Term and termination.
- Return or destruction of PHI on termination.

---

## Audit-Ready Artifacts

| Artifact | Generated by |
|---|---|
| Audit log export (CSV / JSON) | `GET /api/v1/admin/audit-log?format=csv` (planned) |
| Access report per patient MRN | `GET /api/v1/admin/audit-log?patient_mrn_hmac=…` |
| Encryption-at-rest evidence | `SELECT length(subjective) FROM soap_notes` shows ciphertext lengths > plaintext |
| Session timeout evidence | `SessionTimeoutMiddleware` returns 401 after 15 min — captured in `audit_logs` |
| MFA enrollment report | `SELECT email, totp_enabled FROM users` |
| Backup restore drill log | Maintained by Ops (`docs/RUNBOOK.md#monthly-restore-drill`) |
