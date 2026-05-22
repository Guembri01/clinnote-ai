# Data Retention Policy — ClinNote AI

> HIPAA §164.316 requires Covered Entities and Business Associates to retain documentation and certain records for **six years from the date of creation or the date when last in effect, whichever is later**. Clinical content has additional state-specific retention requirements.

## Retention Schedule

| Data class | Storage location | Retention | Disposition |
|---|---|---|---|
| Audio bytes (in-flight) | RAM + Redis (`audio:{session_id}` key) | While transcription in progress | Deleted on transcript completion; orphans purged every 5 min by `purge_stale_audio` |
| Audio bytes (committed) | None | **Zero-retention** | Never persisted to disk or backups |
| Transcripts (raw + corrected) | PG `transcripts` (encrypted) | Linked to session; deleted with parent session | `ON DELETE CASCADE` |
| SOAP notes — DRAFT | PG `soap_notes` (encrypted) | 24 hours from creation | `purge_expired_notes` marks `EXPIRED`; hard-deleted after 7 days |
| SOAP notes — APPROVED | PG `soap_notes` (encrypted) | **7 years** (typical state requirement); 10 years for minors | Cold-storage archive after 2 years; deletion request handled via legal review |
| SOAP notes — EXPIRED | PG `soap_notes` (encrypted) | 7 days from expiry | Hard-delete by `purge_expired_notes` |
| ICD / CPT codes | PG `icd_codes`, `cpt_codes` | Same as parent note | Cascade delete |
| Audit logs | PG `audit_logs` (append-only) | **6 years** minimum | Monthly partitions; partitions older than 6 years moved to cold storage (planned) |
| User accounts (active) | PG `users` | Lifetime of employment + 1 year | Soft delete via `is_active=false`; hard delete after 1 year |
| User accounts (deactivated) | PG `users` | 1 year after deactivation | Hard delete; audit log entries retain `user_id` as nullable FK (`ON DELETE SET NULL`) |
| MFA secrets | PG `users.mfa_secret` (encrypted) | While account active | Zeroed on account deactivation |
| Session metadata (recording_sessions) | PG | 7 years (parent SOAP note retention) | Same as SOAP notes |
| Patient records (`patients`) | PG (encrypted) | While patient has any active SOAP note + 7 years | Manual review for deletion requests |
| FHIR push receipts | PG `soap_notes.fhir_*` | Same as parent note | Cascade |
| Application logs (no PHI) | Cloud logging service | 90 days hot, 13 months warm, deleted | Provider-managed |
| Backups (encrypted) | Cloud-managed | 30 days point-in-time + monthly snapshot 12 months | Provider-managed |

## Beat Schedule (current)

| Task | Frequency | What it does |
|---|---|---|
| `purge_expired_notes` | every 15 min | Mark DRAFT past `expires_at` → EXPIRED; hard-delete EXPIRED > 7 days old |
| `purge_stale_audio` | every 5 min | Surface in-memory buffer counts; clean orphans |
| `archive_old_audit_logs` | daily at 03:00 UTC | Stub — production will move ≥ 6-year-old partitions to cold storage |

See `backend/app/workers/beat_schedule.py`.

## Subject Access Requests (HIPAA §164.524)

A patient (or authorised representative) has the right to inspect or obtain a copy of their PHI.

- Request entry point: customer's covered entity, **not** ClinNote AI directly.
- The CE invokes `GET /api/v1/patients/mrn/{mrn}` plus `GET /api/v1/notes?patient_mrn_hmac=…` to assemble the record.
- Response format: machine-readable JSON + optional PDF render.
- Turnaround: **30 days** from request (state may be tighter).

## Right of Erasure / Deletion Requests

HIPAA does not grant patients a general right of deletion; medical records must be retained for the statutory period. **Deletion requests are routed to legal review.** Pseudonymisation (suppression of identifiers while retaining clinical content for population analytics) is the typical resolution.

## Operational Controls

- **Backups** are encrypted at rest by the cloud provider. They contain ciphertext only — losing a backup does not leak PHI unless the `ENCRYPTION_KEY` is also lost.
- **Test/dev environments** never receive production PHI. Demo data uses synthetic patients (see `scripts/seed_demo.py`).
- **Logs** are scrubbed at write time; the only authorised PHI sink is `audit_logs`.
- **DB user separation** (planned): write-only role for the audit-log inserter, read-only role for the application app server.

## Auditability

For any retention claim above, the operator can produce evidence by:

```sql
-- Confirm zero-retention audio: should always return 0
SELECT COUNT(*) FROM recording_sessions
WHERE audio_deleted_at IS NULL AND status = 'completed';

-- Confirm expired-note purge running:
SELECT COUNT(*) FROM soap_notes
WHERE status = 'expired' AND updated_at < NOW() - INTERVAL '7 days';
-- Expected: 0

-- Confirm audit-log immutability triggers exist:
SELECT trigger_name FROM information_schema.triggers
WHERE event_object_table = 'audit_logs'
  AND action_statement LIKE '%audit_log_no_modify%';
-- Expected: 2 rows (UPDATE + DELETE)
```
