/**
 * Transcript types for ClinNote AI
 */

/** Speaker identification in transcript */
export type Speaker = 'physician' | 'patient' | 'unknown';

/** A single utterance in the transcript */
export interface TranscriptSegment {
  id: string;
  speaker: Speaker;
  text: string;
  start_time: number; // seconds from recording start
  end_time: number;
  confidence: number; // 0-1
}

/** A partial (in-progress) transcript segment received over WebSocket */
export interface PartialTranscript {
  text: string;
  speaker?: Speaker;
  timestamp: number;
  is_final: boolean;
}

/** Complete transcript of a recording session */
export interface Transcript {
  id: string;
  session_id: string;
  segments: TranscriptSegment[];
  full_text: string;
  language: string;
  word_count: number;
  duration_seconds: number;
  created_at: string;
}

/** An edit made to a transcript by a physician */
export interface TranscriptEdit {
  transcript_id: string;
  segment_id: string;
  original_text: string;
  edited_text: string;
  edited_by: string;
  edited_at: string;
}

/** Request to edit a transcript segment */
export interface EditTranscriptRequest {
  segment_id: string;
  text: string;
}
