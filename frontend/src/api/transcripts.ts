/**
 * Transcript API functions for ClinNote AI
 */

import apiClient from './client';
import type { Transcript, EditTranscriptRequest } from '@/types/transcript';

/**
 * Get the transcript for a session
 */
export async function getTranscript(transcriptId: string): Promise<Transcript> {
  const { data } = await apiClient.get<Transcript>(`/transcripts/${transcriptId}`);
  return data;
}

/**
 * Edit a transcript segment
 */
export async function editTranscript(
  transcriptId: string,
  edit: EditTranscriptRequest
): Promise<Transcript> {
  const { data } = await apiClient.patch<Transcript>(`/transcripts/${transcriptId}`, edit);
  return data;
}
