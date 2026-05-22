# Changelog

All notable changes to ClinNote AI are documented here.

## [1.0.0] — 2025-05-17

### Added
- Initial release
- Ambient clinical voice-to-EHR note generator
- Real-time audio streaming and transcription via DeepInfra Whisper v3
- AI SOAP note generation (Subjective/Objective/Assessment/Plan) using GPT-4.1-nano
- HIPAA-compliant AES-256 PHI encryption at rest via Fernet
- Append-only audit logging for all PHI access
- TOTP MFA with account lockout (5 attempts / 5 minutes)
- Session inactivity enforcement (15-minute timeout)
- Zero-retention audio policy
- JWT access (15 min) + refresh (7 day) tokens
- Patient record management with encrypted PHI fields
- Lab report and intake form OCR via Azure Document Intelligence
- HL7 FHIR R4 EHR integration export
- ICD-10-CM code search and lookup
- Physician note review and approval workflow
- Unapproved note auto-expiry after 24 hours
- Admin audit log reporting
- WebSocket real-time transcription streaming
- React SPA with Tailwind CSS dark/navy theme

### Security
- HIPAA-compliant PHI encryption (AES-256 Fernet)
- JWT HS256 with 15-minute access token expiry
- TOTP MFA with account lockout protection
- Append-only audit log for all PHI access
- Session inactivity timeout (900 seconds)
- Security headers: X-Content-Type-Options, X-Frame-Options, HSTS, Referrer-Policy
- Permissions-Policy: geolocation=(), microphone=(), camera=()
