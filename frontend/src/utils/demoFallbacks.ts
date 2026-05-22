/**
 * Demo Fallbacks for ClinNote AI
 *
 * When the backend returns empty / sparse data (e.g. a fresh deploy or
 * the seed script hasn't run yet), these fixtures keep the UI looking
 * "demo-ready" and screenshot-grade. Every fixture below carries a
 * `// FALLBACK` comment so it's grep-able and obvious.
 */

import type { AuditLogEntry, UsageStats, ActiveSession } from '@/types/api';

const MS_PER_MIN = 60_000;
const MS_PER_HOUR = 3_600_000;

/** FALLBACK: realistic audit-log entries for screenshots */
export const DEMO_AUDIT_LOG: AuditLogEntry[] = [
  {
    id: 'demo-1',
    action: 'note.approved',
    resource_type: 'soap_note',
    resource_id: 'note_8a3f2b1c9d',
    user_id: 'u_demo_001',
    user_name: 'Dr. Maria Santos',
    user_role: 'physician',
    ip_address: '10.0.42.18',
    timestamp: new Date(Date.now() - 4 * MS_PER_MIN).toISOString(),
    patient_mrn: 'MRN-09823',
  },
  {
    id: 'demo-2',
    action: 'recording.started',
    resource_type: 'session',
    resource_id: 'sess_7b2e4f1a3c',
    user_id: 'u_demo_002',
    user_name: 'Dr. James Chen',
    user_role: 'physician',
    ip_address: '10.0.42.31',
    timestamp: new Date(Date.now() - 11 * MS_PER_MIN).toISOString(),
    patient_mrn: 'MRN-11402',
  },
  {
    id: 'demo-3',
    action: 'note.fhir_pushed',
    resource_type: 'soap_note',
    resource_id: 'note_3c1a9b7d2e',
    user_id: 'u_demo_001',
    user_name: 'Dr. Maria Santos',
    user_role: 'physician',
    ip_address: '10.0.42.18',
    timestamp: new Date(Date.now() - 18 * MS_PER_MIN).toISOString(),
    patient_mrn: 'MRN-08715',
  },
  {
    id: 'demo-4',
    action: 'auth.login',
    resource_type: 'user',
    resource_id: 'u_demo_003',
    user_id: 'u_demo_003',
    user_name: 'Nurse Patricia Brown',
    user_role: 'nurse',
    ip_address: '10.0.42.55',
    timestamp: new Date(Date.now() - 23 * MS_PER_MIN).toISOString(),
  },
  {
    id: 'demo-5',
    action: 'note.edited',
    resource_type: 'soap_note',
    resource_id: 'note_5e8d2a4b1f',
    user_id: 'u_demo_002',
    user_name: 'Dr. James Chen',
    user_role: 'physician',
    ip_address: '10.0.42.31',
    timestamp: new Date(Date.now() - 31 * MS_PER_MIN).toISOString(),
    patient_mrn: 'MRN-12903',
  },
  {
    id: 'demo-6',
    action: 'icd_code.added',
    resource_type: 'soap_note',
    resource_id: 'note_5e8d2a4b1f',
    user_id: 'u_demo_002',
    user_name: 'Dr. James Chen',
    user_role: 'physician',
    ip_address: '10.0.42.31',
    timestamp: new Date(Date.now() - 33 * MS_PER_MIN).toISOString(),
    patient_mrn: 'MRN-12903',
  },
  {
    id: 'demo-7',
    action: 'transcript.viewed',
    resource_type: 'transcript',
    resource_id: 'txt_2f9d8e7c1b',
    user_id: 'u_demo_004',
    user_name: 'Dr. Aisha Patel',
    user_role: 'physician',
    ip_address: '10.0.42.77',
    timestamp: new Date(Date.now() - 45 * MS_PER_MIN).toISOString(),
    patient_mrn: 'MRN-10548',
  },
  {
    id: 'demo-8',
    action: 'consent.recorded',
    resource_type: 'session',
    resource_id: 'sess_6a3c8b1d2e',
    user_id: 'u_demo_004',
    user_name: 'Dr. Aisha Patel',
    user_role: 'physician',
    ip_address: '10.0.42.77',
    timestamp: new Date(Date.now() - 52 * MS_PER_MIN).toISOString(),
    patient_mrn: 'MRN-10548',
  },
  {
    id: 'demo-9',
    action: 'note.approved',
    resource_type: 'soap_note',
    resource_id: 'note_9f4b3c8e2d',
    user_id: 'u_demo_004',
    user_name: 'Dr. Aisha Patel',
    user_role: 'physician',
    ip_address: '10.0.42.77',
    timestamp: new Date(Date.now() - 1 * MS_PER_HOUR).toISOString(),
    patient_mrn: 'MRN-10548',
  },
  {
    id: 'demo-10',
    action: 'session.completed',
    resource_type: 'session',
    resource_id: 'sess_1e9d2a8b3f',
    user_id: 'u_demo_001',
    user_name: 'Dr. Maria Santos',
    user_role: 'physician',
    ip_address: '10.0.42.18',
    timestamp: new Date(Date.now() - 1.2 * MS_PER_HOUR).toISOString(),
    patient_mrn: 'MRN-09823',
  },
  {
    id: 'demo-11',
    action: 'admin.viewed_audit_log',
    resource_type: 'audit_log',
    resource_id: 'audit_global',
    user_id: 'u_demo_005',
    user_name: 'Admin Steven Lee',
    user_role: 'admin',
    ip_address: '10.0.42.10',
    timestamp: new Date(Date.now() - 1.5 * MS_PER_HOUR).toISOString(),
  },
  {
    id: 'demo-12',
    action: 'mfa.verified',
    resource_type: 'user',
    resource_id: 'u_demo_001',
    user_id: 'u_demo_001',
    user_name: 'Dr. Maria Santos',
    user_role: 'physician',
    ip_address: '10.0.42.18',
    timestamp: new Date(Date.now() - 2 * MS_PER_HOUR).toISOString(),
  },
];

/** FALLBACK: realistic usage stats for screenshots */
export const DEMO_USAGE_STATS: UsageStats = {
  total_sessions: 124,
  total_notes: 118,
  approved_notes: 89,
  pending_approval: 7,
  avg_session_duration_seconds: 612,
  sessions_today: 12,
  notes_generated_today: 10,
  active_physicians: 5,
};

/** FALLBACK: realistic active sessions for the admin live table */
export const DEMO_ACTIVE_SESSIONS: ActiveSession[] = [
  {
    session_id: 'sess_live_001',
    physician_name: 'Dr. Maria Santos',
    physician_id: 'u_demo_001',
    patient_mrn: 'MRN-09823',
    status: 'recording',
    duration_seconds: 372,
    started_at: new Date(Date.now() - 372 * 1000).toISOString(),
  },
  {
    session_id: 'sess_live_002',
    physician_name: 'Dr. James Chen',
    physician_id: 'u_demo_002',
    patient_mrn: 'MRN-11402',
    status: 'recording',
    duration_seconds: 184,
    started_at: new Date(Date.now() - 184 * 1000).toISOString(),
  },
];

/** FALLBACK: 14-day sparkline series for KPI strip */
export const DEMO_SESSIONS_LAST_14_DAYS: number[] = [
  2, 1, 3, 0, 2, 4, 3, 1, 2, 3, 5, 4, 3, 6,
];

/** FALLBACK: today's mock schedule for the dashboard */
export interface ScheduleEntry {
  time: string;
  initials: string;
  complaint: string;
}
export const DEMO_TODAY_SCHEDULE: ScheduleEntry[] = [
  { time: '14:00', initials: 'J.M.', complaint: 'Follow-up — Type 2 DM' },
  { time: '14:30', initials: 'S.K.', complaint: 'New patient — chest pain' },
  { time: '15:15', initials: 'R.A.', complaint: 'Annual physical exam' },
  { time: '16:00', initials: 'T.O.', complaint: 'Hypertension review' },
];

/** FALLBACK: admin sparklines (each is a small series 0-100) */
export const DEMO_ADMIN_SPARKLINES = {
  sessions: [2, 1, 3, 0, 2, 4, 3, 1, 2, 3, 5, 4, 3, 6],
  approvalRate: [88, 90, 91, 89, 92, 93, 94, 93, 95, 96, 96, 97, 96, 97],
  aiLatency: [820, 790, 810, 770, 750, 740, 760, 730, 720, 710, 700, 720, 690, 680],
  fhirPushSuccess: [98, 99, 97, 99, 100, 99, 100, 98, 99, 100, 99, 100, 99, 100],
} as const;

/** FALLBACK: active-users-right-now widget */
export interface ActiveUser {
  initials: string;
  name: string;
  status: 'recording' | 'reviewing' | 'idle';
}
export const DEMO_ACTIVE_USERS: ActiveUser[] = [
  { initials: 'MS', name: 'Dr. Maria Santos', status: 'recording' },
  { initials: 'JC', name: 'Dr. James Chen', status: 'recording' },
  { initials: 'AP', name: 'Dr. Aisha Patel', status: 'reviewing' },
];
