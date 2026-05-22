# Architecture — ClinNote AI

## Overview
ClinNote AI is a HIPAA-compliant ambient clinical voice-to-EHR note generator. Physicians record patient encounters; the system transcribes audio in real time via DeepInfra Whisper v3, then uses GPT-4.1-nano to generate structured SOAP notes that physicians review and approve before EHR integration. All PHI fields are AES-256 encrypted at rest via Fernet.

## System Components

```
┌─────────────────────────────────────────────┐
│                  Browser                    │
│         React SPA (port 3000)               │
└──────────────────┬──────────────────────────┘
                   │ HTTP / REST API + WebSocket
                   ▼
┌─────────────────────────────────────────────┐
│         FastAPI Backend (port 8003)         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  Auth    │  │Clinical  │  │  AI      │  │
│  │  MFA     │  │  Routers │  │ Pipeline │  │
│  └──────────┘  └──────────┘  └──────────┘  │
│  ┌──────────────────────────────────────┐   │
│  │  AuditMiddleware + SessionTimeout    │   │
│  └──────────────────────────────────────┘   │
└────────┬─────────────┬────────────┬─────────┘
         │             │            │
   ┌─────▼────┐  ┌─────▼────┐  ┌───▼──────────────────┐
   │ SQLite / │  │  Redis   │  │  External AI Services  │
   │ PostgreSQL│  │  Cache   │  │  OpenAI / DeepInfra   │
   │(Encrypted│  │(sessions)│  │  Azure DI / FHIR      │
   └──────────┘  └──────────┘  └──────────────────────┘
```

## Key Modules

### Backend (`backend/app/`)
| Module | Responsibility |
|--------|---------------|
| `main.py` | FastAPI app, CORS, HIPAA middleware stack, lifespan hooks |
| `config.py` | Pydantic Settings — all env vars typed and validated |
| `database.py` | Async SQLAlchemy engine and session factory |
| `middleware/audit_middleware.py` | Append-only audit logging for all PHI access |
| `middleware/session_timeout.py` | 15-minute inactivity enforcement |
| `api/v1/auth.py` | JWT auth, TOTP MFA, refresh tokens, account lockout |
| `api/v1/patients.py` | Patient records (PHI AES-256 encrypted at rest) |
| `api/v1/recordings.py` | Recording session lifecycle management |
| `api/v1/transcripts.py` | Transcript access and manual editing |
| `api/v1/notes.py` | SOAP note generation, editing, approval workflow |
| `api/v1/documents.py` | Lab report and intake form OCR |
| `api/v1/fhir.py` | HL7 FHIR R4 EHR integration export |
| `api/v1/icd.py` | ICD-10-CM code search and lookup |
| `api/v1/admin.py` | Admin reporting and audit log review |
| `api/v1/websocket.py` | Real-time audio streaming and transcription events |

### Frontend (`frontend/src/`)
| Module | Responsibility |
|--------|---------------|
| `pages/` | Login, Dashboard, Patients, Recording, Notes pages |
| `components/` | Reusable UI components |
| `lib/api.ts` | Axios API client with JWT interceptor |
| `types/` | TypeScript interfaces mirroring backend schemas |

## Authentication Flow (HIPAA Compliant)
1. User submits email/password to `POST /api/v1/auth/login`
2. If MFA enabled, user submits TOTP code to `POST /api/v1/auth/verify-mfa`
3. Backend returns JWT access token (15 min) + refresh token
4. Session timeout middleware enforces 15-min inactivity limit
5. All PHI access is logged to the append-only audit log
6. Account locked after 5 failed attempts for 5 minutes

## SOAP Note Generation Pipeline
1. Physician starts recording session via `POST /api/v1/recordings`
2. Audio streamed via WebSocket in real time
3. DeepInfra Whisper v3 transcribes to text segments
4. Physician ends session; system auto-generates SOAP note
5. GPT-4.1-nano analyzes transcript and produces structured SOAP format
6. Physician reviews and edits the draft note
7. Physician approves note; system flags for EHR export
8. Optional: `POST /api/v1/fhir/export` sends to EHR via FHIR R4

## PHI Security Model
- All PHI fields encrypted with Fernet AES-256 before storage
- Encryption key must be set in `ENCRYPTION_KEY` env var
- Audit log records every read/write of PHI with user, timestamp, action
- Zero-retention audio policy: audio deleted after transcription
- Session inactivity timeout: 900 seconds (15 minutes)
- Unapproved notes auto-expire after 24 hours
