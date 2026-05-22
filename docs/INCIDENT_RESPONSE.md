# Incident Response Plan — ClinNote AI

> Authoritative playbook for security and availability incidents involving ClinNote AI. Tested at least annually.

## Severity Classification

| Severity | Definition | Examples |
|---|---|---|
| **SEV-1** | Confirmed PHI breach; multi-tenant outage; ransomware | Stolen database backup; live PHI exfiltration; clinical service unavailable > 1 hour |
| **SEV-2** | Suspected PHI exposure; single-tenant outage > 30 min; auth-bypass disclosed | Vuln report with PoC; partial outage; one customer fully blocked |
| **SEV-3** | Service degradation; non-PHI security event | Spike in 5xx errors; rate-limit abuse without breach |
| **SEV-4** | Cosmetic or policy violation | Misconfigured header; out-of-policy log retention |

## Roster (24×7 on-call)

- **Incident Commander** — directs response, sole decision-maker on actions
- **Tech Lead** — diagnoses, executes containment
- **Communications Lead** — drafts notices, talks to customers
- **Legal/Compliance Lead** — assesses HIPAA Breach Notification Rule triggers

Contact rotation in `ops/oncall-schedule.yaml` (not in repo).

## Timeline Obligations

| Event | Deadline |
|---|---|
| Acknowledge alert | 15 minutes (SEV-1/2), 4 hours (SEV-3), next business day (SEV-4) |
| Initial customer notice (suspected breach) | **72 hours** (matches GDPR Art. 33; tighter than HIPAA) |
| HHS notice — breach affecting ≥ 500 individuals | **60 days** (HIPAA §164.404) |
| HHS log — breach affecting < 500 | Annually, ≤ 60 days after year-end |
| Media notice — breach affecting ≥ 500 in a state/jurisdiction | 60 days |
| Postmortem published internally | 5 business days |
| Customer-facing postmortem (anonymised) | 10 business days (SEV-1/2 only) |

## Standard Response Flow

```
┌───────────────┐
│  Detection    │   ← alerting, customer report, vuln disclosure
└───────┬───────┘
        ▼
┌───────────────┐
│  Triage       │   ← assign Severity; declare incident in #incident-clinnote
└───────┬───────┘
        ▼
┌───────────────┐
│  Containment  │   ← stop the bleed: revoke key, kill session, quarantine pod
└───────┬───────┘
        ▼
┌───────────────┐
│  Eradication  │   ← remove root cause: patch, rotate, redeploy
└───────┬───────┘
        ▼
┌───────────────┐
│  Recovery     │   ← restore service from clean state; verify integrity
└───────┬───────┘
        ▼
┌───────────────┐
│  Lessons      │   ← postmortem within 5 business days
└───────────────┘
```

## Containment Quick-Reference

### Suspected PHI breach

1. **Revoke** the suspected access path: deactivate user accounts, rotate API keys, kill JWT secret (forces global re-login).
2. **Snapshot** the relevant `audit_logs` slice and DB state before any further change.
3. **Block** the source IP at the LB.
4. **Notify** Legal + Comms within 60 minutes.

### Stolen `ENCRYPTION_KEY`

1. Rotate the application-side `ENCRYPTION_KEY` immediately.
2. All PHI ciphertexts become undecryptable — accept temporary read failure rather than continued exposure.
3. Begin offline re-encryption from a known-clean backup using both old and new keys (`docs/RUNBOOK.md#encryption-key-rotation`).
4. SEV-1: 72-hour customer notice mandatory; assess HHS reporting.

### Compromised admin account

1. `UPDATE users SET is_active = FALSE WHERE id = '<uuid>'`.
2. Force-expire all sessions: rotate `SECRET_KEY`.
3. `SELECT * FROM audit_logs WHERE user_id = '<uuid>' ORDER BY timestamp DESC` to map blast radius.
4. Reset the user's password + re-enroll MFA after identity verification.

### Worker pool overload / Celery wedge

1. `docker compose ps` to confirm worker health.
2. `celery -A app.workers.celery_app inspect active` shows running tasks.
3. Kill stuck tasks; let `task_acks_late=True` re-queue them.
4. Scale workers horizontally if backlog persists.

### Database corruption / restore drill

1. Switch app to **read-only mode** (planned config flag).
2. Restore from latest verified backup to a separate instance.
3. Verify ciphertext integrity by decrypting a small sample with the current `ENCRYPTION_KEY`.
4. Cut traffic over; retain corrupted instance for forensic analysis.

## Communication Templates

### Initial customer notice (within 72h of suspected breach)

> Subject: **Security Notification — ClinNote AI**
>
> We are writing to inform you that on [DATE], ClinNote AI detected [DESCRIPTION OF EVENT]. We are actively investigating in coordination with [LEGAL/FORENSICS]. At this time we [HAVE / HAVE NOT] confirmed that PHI was accessed.
>
> Immediate actions taken: [LIST].
>
> What we ask of you: [LIST].
>
> A detailed update will follow within [TIMEFRAME]. We will provide a final report upon investigation completion.

### Public postmortem template

- **Summary** (3 sentences max)
- **Impact** (who, how many, what data)
- **Timeline** (UTC)
- **Root cause**
- **Fix**
- **What we're changing**
- **Apology**

## Tools & Channels

| Tool | Use |
|---|---|
| PagerDuty | On-call escalation |
| Slack `#incident-clinnote` | Real-time coordination (single channel per incident) |
| Statuspage | Customer-facing status |
| Notion incident template | Live incident document |
| GitHub Private Security Advisory | Coordinated disclosure |

## Annual Tabletop

A live tabletop exercise is conducted every 12 months. The most recent exercise outcome and action items are appended to this document as an addendum.

---

*Last reviewed: 2026-05-20.*
