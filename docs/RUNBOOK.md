# Operations Runbook — ClinNote AI

> Day-2 operations for ClinNote AI. Audience: on-call engineers and the platform team.

## Quick reference

| Task | Command |
|---|---|
| Tail backend logs | `docker compose logs -f backend` |
| Tail Celery worker | `docker compose logs -f celery_worker` |
| Tail Celery beat | `docker compose logs -f celery_beat` |
| Restart backend (zero-downtime) | `docker compose up -d --no-deps --build backend` |
| Drain a Celery worker | `docker compose exec celery_worker celery -A app.workers.celery_app control shutdown` |
| Open a DB shell | `docker compose exec postgres psql -U postgres clinnote_ai` |
| Force expire all draft notes (manual maintenance) | `docker compose exec celery_worker celery -A app.workers.celery_app call app.workers.maintenance_tasks.purge_expired_notes` |
| Re-seed demo data | `python scripts/seed_demo.py` |

## Healthchecks

| Endpoint | Expectation |
|---|---|
| `GET /health` | `{"status":"healthy","components":{"database":"ok","encryption":"configured"}}` |
| `GET /docs` | 200, Swagger UI loads |
| `WS /ws/recording/{session_id}` (manual) | 401 without token; 1006 on bad subprotocol |

If `/health` shows `encryption: warning: not set` in production — **page immediately**. New PHI writes will be unrecoverable on next restart.

## Deploys

### Production deploy
1. PR merged to `main` after review + green CI.
2. Tag `vX.Y.Z`.
3. CI builds Docker images and pushes to the registry.
4. Apply: `kubectl set image deployment/backend backend=registry/clinnote-backend:vX.Y.Z` (or `docker compose pull && docker compose up -d`).
5. Monitor `/health` and the request-rate dashboard for 30 minutes.
6. Run smoke tests: login → start session → stop → list notes.

### Rollback
- `kubectl rollout undo deployment/backend` OR `docker compose up -d backend=registry/clinnote-backend:vX.Y.(Z-1)`.
- If the DB migration changed schema, **do not auto-roll-back the DB** — confirm forward-only path with the on-call.

## Backups & Restore

- **Backups**: cloud-managed PostgreSQL automated daily backups + WAL archival. 30-day point-in-time recovery.
- **Monthly restore drill**: every 1st Tuesday at 10:00 UTC.
  1. Spin up a restore target in a non-prod project.
  2. Restore latest backup; verify schema and row counts.
  3. Decrypt one row of each PHI table using the current `ENCRYPTION_KEY` to confirm key-data alignment.
  4. Record drill result in `ops/restore-drill-log.md`.

## Encryption Key Rotation

> Until key-versioning ships (v1.1), this is a controlled outage event.

1. Schedule a maintenance window (low traffic; coordinate with customers).
2. Take a fresh backup of the production DB.
3. Generate new key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
4. Run the rotation script (offline, against the **restored snapshot**):
   - Decrypt every PHI column with the **old** key.
   - Re-encrypt with the **new** key.
   - Recompute every `mrn_hmac`.
5. Validate by spot-decrypting 100 rows.
6. Swap the production DB to the rotated copy.
7. Update Docker Secret / Vault entry with the new `ENCRYPTION_KEY`.
8. Restart all backend pods and Celery workers.
9. Verify `/health` and run smoke tests.
10. Destroy the old `ENCRYPTION_KEY` from all stores; record in audit ledger.

## Common Failure Modes

### Backend pod crashloops with `ENCRYPTION_KEY too short`
- Verify `ENCRYPTION_KEY` is exactly 44 chars (URL-safe base64 of 32 bytes).
- If missing, restore from the Secret manager (never regenerate — that orphans existing PHI).

### Login returns 429 broadly
- Check `app.rate_limit` settings — should be `5/minute` per IP.
- If a corporate proxy NATs all clients to one IP, raise the limit for that org by IP allowlist.

### Celery beat stops running scheduled tasks
- `docker compose ps celery_beat` — confirm container is alive.
- Beat schedule file: `app/workers/beat_schedule.py`.
- Restart: `docker compose restart celery_beat`.

### Audit log inserts failing
- Check that the trigger `audit_log_no_modify()` is not firing on INSERT (it should only fire on UPDATE/DELETE).
- `\d+ audit_logs` in psql shows triggers; verify event is `UPDATE` or `DELETE`, not `INSERT`.

### WebSocket disconnects mid-recording
- Browser DevTools → Network → WS frame inspector.
- Backend logs filter for `recording_websocket`.
- Confirm Nginx `proxy_read_timeout` is ≥ 3600 (default 60 will kill long sessions).

### FHIR push stuck on `pending`
- Inspect: `SELECT id, fhir_push_status, fhir_resource_id FROM soap_notes WHERE fhir_push_status = 'pending';`
- Likely cause: external EHR endpoint unreachable or OAuth token expired.
- Manual retry: `POST /api/v1/fhir/push/{note_id}` (idempotent).

### High AI cost / OpenAI bill spike
- Check `audit_logs` for unusual SOAP-generation volume.
- Confirm Celery rate limits in `celery_app.py` (`20/m` for notes).
- If under attack, add per-user note-generation quotas (planned).

## Scaling

| Component | Scaling approach |
|---|---|
| FastAPI backend | Horizontal — stateless behind LB; sticky sessions only required for WebSocket |
| WebSocket | Sticky session by `session_id`; once we move audio buffers to Redis, fully horizontal |
| Postgres | Vertical first (RDS); read replicas for `audit_logs` queries; partitioning by month for audit table |
| Redis | Sentinel/Cluster for HA; sized for in-flight audio capacity = (concurrent_sessions × 120 min × bitrate) |
| Celery workers | Add workers per queue: `transcription`, `notes`. Each worker prefetch=1 |

## Capacity Sizing (rough)

- 1 physician ≈ 25 encounters/day = 25 sessions × 12 min average × 16 kHz audio ≈ 35 MB Redis at peak per physician.
- 1000 active physicians ≈ 35 GB Redis at peak + 25k Celery jobs/day per type.
- DB growth ≈ 25k notes/day × ~4 KB ciphertext × 1000 physicians ≈ 100 MB/day SOAP + similar for audit.

## On-call Hand-off

End of shift: post a one-line summary in `#oncall-handoff` with any open incidents, recent customer escalations, or rollouts in flight.
