/**
 * Recording session API functions for ClinNote AI
 */

import apiClient from './client';
import type { RecordingSession, StartRecordingRequest } from '@/types/recording';
import type { PaginatedResponse, PaginationParams } from '@/types/api';

/**
 * Start a new recording session
 */
export async function startRecording(payload: StartRecordingRequest): Promise<RecordingSession> {
  const { data } = await apiClient.post('/recordings/start', {
    patient_mrn: payload.patient.mrn,
    encounter_id: payload.patient.encounter_id,
    session_metadata: {
      first_name: payload.patient.first_name,
      last_name: payload.patient.last_name,
      date_of_birth: payload.patient.date_of_birth,
      chief_complaint: payload.patient.chief_complaint,
    },
  });
  return {
    id: data.id,
    patient: payload.patient,
    physician_id: data.user_id,
    status: data.status,
    consent: null,
    duration_seconds: data.duration_seconds ?? 0,
    lab_document_ids: payload.lab_document_ids ?? [],
    created_at: data.created_at,
    updated_at: data.updated_at,
  };
}

/**
 * Stop the current recording session
 */
export async function stopRecording(sessionId: string): Promise<RecordingSession> {
  const { data } = await apiClient.post<RecordingSession>(`/recordings/${sessionId}/stop`);
  return data;
}

/**
 * Pause recording
 */
export async function pauseRecording(sessionId: string): Promise<RecordingSession> {
  const { data } = await apiClient.post<RecordingSession>(`/recordings/${sessionId}/pause`);
  return data;
}

/**
 * Resume a paused recording
 */
export async function resumeRecording(sessionId: string): Promise<RecordingSession> {
  const { data } = await apiClient.post<RecordingSession>(`/recordings/${sessionId}/resume`);
  return data;
}

/**
 * Get a recording session by ID
 */
export async function getRecording(sessionId: string): Promise<RecordingSession> {
  const { data } = await apiClient.get<RecordingSession>(`/recordings/${sessionId}`);
  return data;
}

/**
 * Get paginated list of recording sessions
 */
export async function getRecordings(
  params?: PaginationParams & { status?: string }
): Promise<PaginatedResponse<RecordingSession>> {
  const { data } = await apiClient.get<PaginatedResponse<RecordingSession>>('/recordings', {
    params,
  });
  return data;
}
