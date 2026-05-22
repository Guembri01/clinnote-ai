/**
 * SOAP Note API functions for ClinNote AI
 */

import apiClient from './client';
import type { SOAPNote, EditNoteRequest, NoteHistoryEntry } from '@/types/soap';
import type { PaginatedResponse, PaginationParams, DateRangeFilter } from '@/types/api';

/**
 * Get a SOAP note by ID
 */
export async function getNote(noteId: string): Promise<SOAPNote> {
  const { data } = await apiClient.get<SOAPNote>(`/notes/${noteId}`);
  return data;
}

/**
 * Edit a SOAP note section or codes
 */
export async function editNote(noteId: string, payload: EditNoteRequest): Promise<SOAPNote> {
  const { data } = await apiClient.patch<SOAPNote>(`/notes/${noteId}`, payload);
  return data;
}

/**
 * Approve a SOAP note — moves status to 'approved'
 */
export async function approveNote(noteId: string): Promise<SOAPNote> {
  const { data } = await apiClient.post<SOAPNote>(`/notes/${noteId}/approve`);
  return data;
}

/**
 * Trigger AI note generation from a completed recording session
 */
export async function generateNote(sessionId: string): Promise<SOAPNote> {
  const { data } = await apiClient.post<SOAPNote>(`/notes/generate`, { session_id: sessionId });
  return data;
}

/**
 * Push an approved note to the EHR via FHIR
 */
export async function pushToFHIR(noteId: string): Promise<SOAPNote> {
  const { data } = await apiClient.post<SOAPNote>(`/notes/${noteId}/fhir-push`);
  return data;
}

/**
 * Get paginated notes history
 */
export async function getNotesHistory(
  params?: PaginationParams & DateRangeFilter & { status?: string }
): Promise<PaginatedResponse<NoteHistoryEntry>> {
  const { data } = await apiClient.get<PaginatedResponse<NoteHistoryEntry>>('/notes', { params });
  return data;
}

/**
 * Voice ↔ SOAP cross-validation audit result (Phase D).
 */
export interface VoiceAuditResult {
  status: string;
  mode: string | null;
  note_id: string;
  transcript_excerpt: string;
  decision: string | null;
  critical_unescalated: unknown[];
  missing_allergies_in_note: unknown[];
  missing_meds_in_plan: unknown[];
  missing_vitals_in_objective: unknown[];
  uncoded_icd: unknown[];
  uncoded_cpt: unknown[];
  talking_points: string[];
}

/**
 * Run the voice ↔ SOAP cross-validation audit on a note.
 */
export async function runVoiceAudit(noteId: string): Promise<VoiceAuditResult> {
  const { data } = await apiClient.post<VoiceAuditResult>(`/notes/${noteId}/voice-audit`);
  return data;
}

/**
 * Download the clinical-QA brief PDF for a note.
 */
export async function downloadClinicalQABrief(noteId: string): Promise<Blob> {
  const { data } = await apiClient.get<Blob>(`/notes/${noteId}/clinical-qa-brief.pdf`, {
    responseType: 'blob',
  });
  return data;
}

/**
 * Phase E — persisted voice transcript for a SOAP note.
 */
export interface NoteVoiceTranscript {
  id: string;
  session_id: string;
  voice_transcript: string;
  transcript_status: string;
  provider: string | null;
  language: string | null;
  confidence: number | null;
  word_count: number | null;
  created_at: string | null;
}

/**
 * Fetch the decrypted voice transcript for a SOAP note (Phase E).
 */
export async function getNoteTranscript(noteId: string): Promise<NoteVoiceTranscript[]> {
  const { data } = await apiClient.get<NoteVoiceTranscript[]>(`/notes/${noteId}/transcript`);
  return data;
}
