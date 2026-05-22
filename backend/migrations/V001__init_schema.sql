-- ClinNote AI — V001 Initial Schema
-- PostgreSQL 14+ (HIPAA-compliant ambient clinical documentation)

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── ENUM TYPES ───────────────────────────────────────────────────────────────
DO $$ BEGIN
    CREATE TYPE user_role_enum AS ENUM ('admin','physician','nurse','pa','viewer');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE session_status_enum AS ENUM (
        'pending_consent','recording','paused','completed','failed'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE note_status_enum AS ENUM ('draft','approved','expired');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE audit_action_enum AS ENUM (
        'LOGIN','LOGOUT','LOGIN_FAILED','MFA_VERIFIED','MFA_FAILED',
        'ACCOUNT_LOCKED','VIEW_PHI','CREATE_PATIENT','VIEW_PATIENT',
        'CREATE_SESSION','START_RECORDING','STOP_RECORDING','CONSENT_RECORDED',
        'VIEW_TRANSCRIPT','EDIT_TRANSCRIPT','CREATE_NOTE','VIEW_NOTE',
        'EDIT_NOTE','APPROVE_NOTE','DELETE_NOTE','FHIR_PUSH','FHIR_PUSH_FAILED',
        'UPLOAD_DOCUMENT','EXPORT_DATA','ADMIN_ACTION','PASSWORD_CHANGE',
        'USER_CREATED','USER_DEACTIVATED'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ─── USERS ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id                     UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    email                  VARCHAR(255)   NOT NULL UNIQUE,
    first_name             VARCHAR(100)   NOT NULL,
    last_name              VARCHAR(100)   NOT NULL,
    hashed_password        VARCHAR(255)   NOT NULL,
    role                   user_role_enum NOT NULL DEFAULT 'viewer',
    specialty              VARCHAR(100),
    npi_number             VARCHAR(20)    UNIQUE,
    org_id                 VARCHAR(100),
    ehr_system             VARCHAR(100),
    is_active              BOOLEAN        NOT NULL DEFAULT TRUE,
    failed_login_attempts  INTEGER        NOT NULL DEFAULT 0,
    locked_until           TIMESTAMPTZ,
    totp_enabled           BOOLEAN        NOT NULL DEFAULT FALSE,
    mfa_secret             TEXT,
    created_at             TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role  ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_org   ON users(org_id);

-- ─── PATIENTS ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS patients (
    id             UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    mrn            TEXT    NOT NULL UNIQUE,
    mrn_hmac       VARCHAR(64) UNIQUE,
    enc_first_name TEXT,
    enc_last_name  TEXT,
    enc_dob        TEXT,
    encounter_id   VARCHAR(100),
    org_id         VARCHAR(100),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_patients_mrn      ON patients(mrn);
CREATE INDEX IF NOT EXISTS idx_patients_mrn_hmac ON patients(mrn_hmac);
CREATE INDEX IF NOT EXISTS idx_patients_org      ON patients(org_id);

-- ─── RECORDING SESSIONS ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS recording_sessions (
    id                  UUID                 PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID                 NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    patient_mrn         TEXT,
    encounter_id        VARCHAR(100),
    status              session_status_enum  NOT NULL DEFAULT 'pending_consent',
    consent_recorded_at TIMESTAMPTZ,
    consent_ip          VARCHAR(50),
    start_time          TIMESTAMPTZ,
    end_time            TIMESTAMPTZ,
    duration_seconds    INTEGER,
    audio_deleted_at    TIMESTAMPTZ,
    session_metadata    JSON,
    created_at          TIMESTAMPTZ          NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ          NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_user        ON recording_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status      ON recording_sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_patient_mrn ON recording_sessions(patient_mrn);
CREATE INDEX IF NOT EXISTS idx_sessions_created     ON recording_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_encounter   ON recording_sessions(encounter_id);

-- ─── TRANSCRIPTS ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS transcripts (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id     UUID        NOT NULL UNIQUE REFERENCES recording_sessions(id) ON DELETE CASCADE,
    raw_text       TEXT,
    corrected_text TEXT,
    diarization    JSON,
    word_count     INTEGER,
    language       VARCHAR(10),
    confidence     FLOAT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (raw_text IS NOT NULL OR corrected_text IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_transcripts_session ON transcripts(session_id);

-- ─── SOAP NOTES ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS soap_notes (
    id                  UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID             NOT NULL REFERENCES recording_sessions(id) ON DELETE CASCADE,
    user_id             UUID             NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    patient_mrn         TEXT,
    status              note_status_enum NOT NULL DEFAULT 'draft',
    expires_at          TIMESTAMPTZ,
    subjective          TEXT,
    objective           TEXT,
    assessment          TEXT,
    plan                TEXT,
    original_ai_content JSON,
    physician_edits     JSON,
    specialty           VARCHAR(100),
    approved_at         TIMESTAMPTZ,
    approved_by         UUID             REFERENCES users(id) ON DELETE SET NULL,
    fhir_push_status    VARCHAR(50),
    fhir_resource_id    VARCHAR(255),
    created_at          TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ      NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_soap_session   ON soap_notes(session_id);
CREATE INDEX IF NOT EXISTS idx_soap_user      ON soap_notes(user_id);
CREATE INDEX IF NOT EXISTS idx_soap_status    ON soap_notes(status);
CREATE INDEX IF NOT EXISTS idx_soap_expires   ON soap_notes(expires_at);
CREATE INDEX IF NOT EXISTS idx_soap_patient   ON soap_notes(patient_mrn);

-- ─── ICD CODES ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS icd_codes (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    note_id     UUID        NOT NULL REFERENCES soap_notes(id) ON DELETE CASCADE,
    code        VARCHAR(20) NOT NULL,
    description VARCHAR(500) NOT NULL,
    confidence  FLOAT,
    is_primary  BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (note_id, code)
);

CREATE INDEX IF NOT EXISTS idx_icd_note    ON icd_codes(note_id);
CREATE INDEX IF NOT EXISTS idx_icd_code    ON icd_codes(code);
CREATE INDEX IF NOT EXISTS idx_icd_primary ON icd_codes(is_primary) WHERE is_primary = TRUE;

-- ─── CPT CODES ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cpt_codes (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    note_id     UUID        NOT NULL REFERENCES soap_notes(id) ON DELETE CASCADE,
    code        VARCHAR(20) NOT NULL,
    description VARCHAR(500) NOT NULL,
    confidence  FLOAT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (note_id, code)
);

CREATE INDEX IF NOT EXISTS idx_cpt_note ON cpt_codes(note_id);
CREATE INDEX IF NOT EXISTS idx_cpt_code ON cpt_codes(code);

-- ─── AUDIT LOGS (HIPAA — append-only) ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    id            UUID              PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID              REFERENCES users(id) ON DELETE SET NULL,
    action        audit_action_enum NOT NULL,
    resource_type VARCHAR(100),
    resource_id   TEXT,
    patient_mrn   TEXT,
    ip_address    VARCHAR(50),
    user_agent    TEXT,
    details       TEXT,
    timestamp     TIMESTAMPTZ       NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_user      ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_action    ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_resource  ON audit_logs(resource_type, resource_id);

-- ─── AUTO-UPDATE TRIGGER ──────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE OR REPLACE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER trg_patients_updated_at
BEFORE UPDATE ON patients FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER trg_sessions_updated_at
BEFORE UPDATE ON recording_sessions FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER trg_transcripts_updated_at
BEFORE UPDATE ON transcripts FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER trg_soap_notes_updated_at
BEFORE UPDATE ON soap_notes FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ─── AUDIT LOG IMMUTABILITY (HIPAA §164.312(b)) ─────────────────────────────
CREATE OR REPLACE FUNCTION audit_log_no_modify()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs is append-only — UPDATE/DELETE not permitted (HIPAA §164.312(b))'
      USING ERRCODE = '42501';
END;
$$;

DROP TRIGGER IF EXISTS trg_audit_logs_no_update ON audit_logs;
CREATE TRIGGER trg_audit_logs_no_update
BEFORE UPDATE ON audit_logs
FOR EACH ROW EXECUTE FUNCTION audit_log_no_modify();

DROP TRIGGER IF EXISTS trg_audit_logs_no_delete ON audit_logs;
CREATE TRIGGER trg_audit_logs_no_delete
BEFORE DELETE ON audit_logs
FOR EACH ROW EXECUTE FUNCTION audit_log_no_modify();
