# Security Policy — ClinNote AI

> ClinNote AI processes Protected Health Information (PHI). Security is a first-class engineering concern, not a release-time concern.

## Reporting a Vulnerability

Report security issues privately to **security@clinnote.ai** (or open a **Private Security Advisory** if the repo is on GitHub). Do **not** open a public issue.

- We acknowledge within **24 hours**.
- We provide a triage decision within **72 hours**.
- We aim to fix CVSS ≥ 7 issues within **7 calendar days**.
- We coordinate disclosure with the reporter.

## Scope

| In scope | Out of scope |
|---|---|
| Authentication, JWT, MFA, session management | Third-party LLM jailbreaks against our system prompts |
| PHI encryption at rest / in transit | DoS via expensive AI calls (handled via rate limits) |
| HIPAA audit log integrity | Social engineering against our staff |
| RBAC bypass | Self-XSS, missing best-practice headers on docs-only routes |
| Supply-chain compromise of dependencies | Issues already documented in this file as accepted risk |

## Security Architecture

### Encryption

| Surface | Mechanism |
|---|---|
| PHI at rest | Fernet (AES-128-CBC + HMAC-SHA256) per field on every PHI column in PostgreSQL. The application-layer encryption key is loaded from `ENCRYPTION_KEY` and validated at startup. |
| PHI in transit | TLS 1.3 enforced at the load balancer / Nginx. HSTS preload header. No HTTP fallback. |
| Audio (in-flight) | Streamed over WSS only. Buffered in-memory or Redis during transcription, deleted after transcript is produced. |
| Database backups | At-rest encryption via the cloud provider (RDS / Cloud SQL) plus application-layer ciphertext (defence in depth). |
| Secrets in transit | Docker Secrets / cloud Secrets Manager in production. Never via env files. |

### Identity & Access

- JWT HS256, 15-minute access tokens, 7-day refresh tokens.
- TOTP-based MFA (RFC 6238), optional for now, **required for clinical staff in production**.
- Account lockout: 5 failed attempts → locked 5 minutes.
- Rate limits: `5/minute` on `/auth/login` and `/auth/verify-mfa` per IP.
- Session inactivity timeout: 15 minutes (HIPAA §164.312(a)(2)(iii)).
- RBAC: `admin > physician > nurse > pa > viewer`.

### Audit Logging

- All PHI access and clinical mutations append to `audit_logs`.
- `audit_logs` is enforced **append-only at the database level** via PL/pgSQL triggers — `UPDATE` and `DELETE` raise `42501`.
- Each entry records: user_id, action, resource_type, resource_id, encrypted patient_mrn, IP address, user agent, free-text details, timestamp.
- Failed authentication attempts logged with reason (`LOGIN_FAILED_ANONYMOUS`).

### WebSocket Authentication

- Production clients **must** send the JWT via the `Sec-WebSocket-Protocol` header (subprotocol `bearer`).
- The `?token=…` query string path is **deprecated** and emits a server-side warning — JWTs in URLs leak into HTTP access logs and browser history.

## Key Rotation

| Key | Rotation cadence | Procedure |
|---|---|---|
| `SECRET_KEY` (JWT) | 90 days | Rotate; existing tokens expire within 15 minutes; users re-auth. |
| `ENCRYPTION_KEY` (PHI) | Annually OR on suspected compromise | Requires a **key-versioning migration** (see `docs/RUNBOOK.md#encryption-key-rotation`). Not yet automated. |
| OpenAI / DeepInfra / Azure API keys | 90 days, or on personnel change | Rotate in the provider, update Docker Secret, redeploy. |
| Database password | 180 days | Rotate via cloud secret manager, restart pods. |
| Mutual-TLS / client certs (if used for FHIR) | Per certificate validity (≤ 397 days). | Renew before expiry; alert at 30 days remaining. |

## Trusted Subprocessors

| Vendor | Purpose | BAA required |
|---|---|---|
| OpenAI | GPT-4.1-nano SOAP generation | **Yes** — sign Anthropic/OpenAI healthcare BAA |
| DeepInfra | Whisper Large v3 transcription | **Yes** |
| Microsoft Azure | Document Intelligence OCR | **Yes** |
| AWS / GCP (host) | Compute, storage, DB | **Yes** |
| Sentry (planned) | Application monitoring | **Yes** — opt-in PII scrubbing required |

A signed BAA must be on file **before** any production traffic flows.

## Coding Standards (security-relevant)

- No raw SQL string concatenation; SQLAlchemy parameterised queries only.
- No `eval`, no `exec`, no `pickle.loads` on untrusted input.
- No PHI in log lines. The audit log is the only authorised PHI sink.
- All inbound user input validated through Pydantic schemas with strict types.
- All outbound HTTP calls have explicit timeouts.
- Dependencies pinned; `pip-audit` and `npm audit` run in CI on every PR.

## Accepted Risks (and Mitigations)

| Risk | Mitigation |
|---|---|
| In-memory audio buffer in `app/api/v1/websocket.py` does not survive worker restart | Single-instance only; planned: move to Redis with 2-hour TTL. Tracked in `RUNBOOK.md`. |
| Fernet uses AES-128 (not AES-256) under the hood | Cleared by HIPAA encryption requirements (NIST SP 800-111 allows AES-128). Documented openly to avoid false claims. |
| `ENCRYPTION_KEY` has no version prefix | Rotation requires offline re-encrypt today; key-version prefix planned for v1.1. |
| `metadata.create_all()` runs on startup alongside Alembic | Production deploys must set `ENVIRONMENT=production` so the auto-create is suppressed (controlled by a single config flag — see `app/main.py:lifespan`). |

## Disclosure Hall of Fame

Researchers who responsibly disclose are acknowledged here with their consent (no payments, no swag — a healthcare-grade thank-you).
