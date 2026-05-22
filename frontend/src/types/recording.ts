/**
 * Recording session types for ClinNote AI
 */

/** Recording session status lifecycle */
export type SessionStatus =
  | 'pending'
  | 'consent_obtained'
  | 'recording'
  | 'paused'
  | 'processing'
  | 'completed'
  | 'failed'
  | 'cancelled';

/** Consent languages supported */
export type ConsentLanguage = 'en' | 'es' | 'fr';

/** Patient consent record */
export interface ConsentRecord {
  consented: boolean;
  language: ConsentLanguage;
  timestamp: string;
  method: 'verbal' | 'emergency_exception';
  recorded_by: string;
}

/** Patient information for a session */
export interface PatientInfo {
  mrn: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  encounter_id: string;
  chief_complaint?: string;
}

/** A recording session object */
export interface RecordingSession {
  id: string;
  patient: PatientInfo;
  physician_id: string;
  status: SessionStatus;
  consent: ConsentRecord | null;
  duration_seconds: number;
  audio_file_url?: string;
  lab_document_ids: string[];
  created_at: string;
  updated_at: string;
  transcript_id?: string;
  note_id?: string;
  error_message?: string;
}

/** Request to start a new recording session */
export interface StartRecordingRequest {
  patient: PatientInfo;
  consent: ConsentRecord;
  lab_document_ids?: string[];
}

/** Consent request data */
export interface ConsentRequest {
  session_id: string;
  language: ConsentLanguage;
  consented: boolean;
  method: 'verbal' | 'emergency_exception';
}

/** A partial transcript segment from real-time WebSocket streaming */
export interface PartialTranscript {
  text: string;
  speaker?: 'physician' | 'patient' | 'unknown';
  timestamp?: number | string;
  is_final?: boolean;
}

/** Audio chunk sent over WebSocket */
export interface AudioChunkMessage {
  type: 'audio_chunk';
  data: string; // base64 encoded audio
  chunk_index: number;
  session_id: string;
}

/** Stop recording message */
export interface StopRecordingMessage {
  type: 'stop_recording';
  session_id: string;
}

/** WebSocket messages received from server */
export type WSInboundMessage =
  | { type: 'partial_transcript'; text: string; speaker?: string }
  | { type: 'processing'; progress?: number }
  | { type: 'transcript_ready'; session_id: string; transcript_id: string }
  | { type: 'error'; message: string; code?: string }
  | { type: 'connected'; session_id: string };

/** WebSocket messages sent to server */
export type WSOutboundMessage = AudioChunkMessage | StopRecordingMessage;
