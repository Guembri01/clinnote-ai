# Threat Model — ClinNote AI

> STRIDE analysis of the ClinNote AI ambient clinical documentation platform. Last reviewed: 2026-05-20.

## System Diagram (text)

```
┌─────────────────────────┐
│  Browser (React PWA)    │ ◄── physician/admin via TLS 1.3
└──────────┬──────────────┘
           │ HTTPS + WSS
           ▼
┌─────────────────────────┐
│  Nginx (TLS termination)│
└──────────┬──────────────┘
           │ HTTP (internal)
           ▼
┌─────────────────────────┐
│  FastAPI (Uvicorn)      │ ◄── JWT auth, middleware stack
└─────┬─────────┬─────────┘
      │         │
      ▼         ▼
┌─────────┐  ┌──────────┐
│ Postgres│  │  Redis   │ ◄── Celery broker + in-flight audio
│  (PHI   │  │ (broker, │
│ Fernet) │  │  audio)  │
└─────────┘  └────┬─────┘
                  │
                  ▼
            ┌──────────────┐
            │  Celery      │ ◄── transcription + SOAP workers
            └────┬─────────┘
                 │ HTTPS (with subprocessor BAA)
                 ▼
      ┌────────────────────────────┐
      │  OpenAI · DeepInfra · Azure │
      └────────────────────────────┘
```

## Trust Boundaries

1. Internet ↔ Nginx (untrusted ↔ DMZ)
2. Nginx ↔ FastAPI (DMZ ↔ application tier)
3. FastAPI ↔ Postgres/Redis (application ↔ data tier)
4. Celery ↔ External AI APIs (data tier ↔ third-party processors)

---

## STRIDE per Component

### Browser / Frontend

| Threat | Vector | Mitigation |
|---|---|---|
| **S** Spoofing | Stolen JWT replay | `sessionStorage` (clears on tab close), 15-min access TTL, refresh rotation |
| **T** Tampering | XSS injecting into note review | Strict CSP, no `dangerouslySetInnerHTML`, Zod validation, react-hook-form |
| **R** Repudiation | "I didn't approve that note" | Server-side `approved_by` + `audit_logs.APPROVE_NOTE` with IP + UA |
| **I** Info disclosure | Browser cache PHI | `Cache-Control: no-store` on every response; PWA service worker excludes `/api/*` from cache |
| **D** DoS | Tab spam, large file upload | API gateway rate limits, 30-second client timeout, 50MB max upload |
| **E** Elevation | Hidden `requiredRole` bypass | RBAC enforced **server-side**; frontend role check is UX only |

### FastAPI Application

| Threat | Vector | Mitigation |
|---|---|---|
| **S** | Forged JWT | HS256 with 64-char secret; algorithm explicitly verified; future migration to RS256 + key rotation |
| **T** | SQL injection | SQLAlchemy parameterised queries only; no raw f-string SQL |
| **R** | Audit log tampering | PL/pgSQL trigger prevents UPDATE/DELETE on `audit_logs` |
| **I** | PHI in logs | Logging middleware redacts; only audit log writes PHI (encrypted MRN) |
| **D** | Brute-force login | `5/minute` per IP rate limit + 5-attempt account lockout |
| **D** | Expensive AI calls | Celery rate limits (`10/m` transcription, `20/m` notes) |
| **E** | Privilege escalation | `require_roles()` dependency enforced on every admin endpoint |

### WebSocket (audio streaming)

| Threat | Vector | Mitigation |
|---|---|---|
| **S** | JWT leaked in URL access logs | `Sec-WebSocket-Protocol` header auth (preferred); query-string deprecated with warning |
| **T** | Crafted audio chunk to crash worker | Base64-decode in try/except; max chunk size cap; chunk_index gap detection |
| **R** | Disowning a recording | Session linked to `user_id` at start; WS validates ownership before accepting frames |
| **I** | Audio leaving the trust boundary | Bytes flow only browser → backend → DeepInfra (BAA) → discard |
| **D** | Open WS forever | Auto-stop at `RECORDING_MAX_DURATION` (120 min); idle disconnect after 60 s |
| **E** | Cross-session injection | Session ID validated against authenticated user_id |

### PostgreSQL

| Threat | Vector | Mitigation |
|---|---|---|
| **S** | DB user impersonation | Single role today; planned write-only role for audit_logs |
| **T** | Direct DB UPDATE of audit_logs | Trigger raises `42501`; even superuser must `DISABLE TRIGGER` (logged) |
| **R** | DB-level row deletion | Triggers + cloud provider audit log + WAL archival |
| **I** | Backup leak | Backups encrypted by cloud provider AND contain only Fernet ciphertext |
| **D** | Query of death | Connection pool sized; statement timeout (planned 30 s); slow query log |
| **E** | DB superuser compromise | Application role is non-superuser; secrets in Docker Secrets/Vault |

### Redis (broker + in-flight audio)

| Threat | Vector | Mitigation |
|---|---|---|
| **S** | Unauthenticated client | `requirepass` + Redis ACLs; in production behind VPC only |
| **T** | Modified message in transit | Internal-only network; TLS optional for Redis 6+ |
| **I** | Audio bytes in Redis longer than 24h | TTL on every audio key; beat task sweeps stale buffers |
| **D** | Memory exhaustion | `maxmemory` + `allkeys-lru` eviction policy |

### External AI APIs (OpenAI, DeepInfra, Azure)

| Threat | Vector | Mitigation |
|---|---|---|
| **S** | Provider spoofing | TLS pinning of provider endpoints (planned) |
| **T** | Provider tampering with PHI | BAA in force; encrypted in transit; we re-encrypt the response before storage |
| **R** | Provider denial of processing | We retain the prompt/request_id; audit log records the call |
| **I** | Prompt-injection causing PHI leak | System prompt hardened; user input wrapped in clear delimiters; output validated against schema |
| **D** | Rate-limit DoS by us | Exponential backoff; circuit breaker on consecutive 5xx |

---

## Top 10 Highest-Risk Findings (current state)

1. ✅ **Login brute-force** — fixed by `@limiter.limit("5/minute")` on `/auth/login` + lockout.
2. ✅ **PHI loss on `ENCRYPTION_KEY` absence** — fixed by RuntimeError in production on empty key.
3. ✅ **JWT in WebSocket query string** — fixed by subprotocol header support; legacy path deprecated.
4. ✅ **`audit_logs` mutability** — fixed by `BEFORE UPDATE/DELETE` trigger.
5. ✅ **`soap_notes.patient_mrn VARCHAR(255)` truncation** — fixed to `TEXT`.
6. ⚠️ **No `ENCRYPTION_KEY` rotation** — accepted risk until v1.1 ships key-versioning.
7. ⚠️ **In-memory `_audio_buffers`** — single-instance limitation; planned migration to Redis with TTL.
8. ⚠️ **No mutual TLS for FHIR push** — depends on EHR partner support.
9. ⚠️ **No formal SBOM / dependency-pinning hashes** — `pip-audit` + `npm audit` planned in CI.
10. ⚠️ **No automated DR / restore drill** — manual monthly drill documented in RUNBOOK; needs to be tested.

---

## Out-of-scope Threats

- Physical security of the cloud datacenter (HIPAA-eligible cloud provider's responsibility).
- Workforce social engineering (HR + security-awareness training).
- Customer-side endpoint compromise (BYOD policy in customer's contract).
- LLM hallucinated diagnoses (clinical sign-off by physician is the control — every note requires a `approved_by` user_id before EHR push).

## Review Cadence

This document is reviewed at least annually, after every production security incident, and whenever a new external subprocessor is added.
