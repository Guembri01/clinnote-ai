/**
 * SOAP Note and clinical coding types for ClinNote AI
 */

/** Status of a SOAP note in its lifecycle */
export type NoteStatus = 'generating' | 'draft' | 'approved' | 'expired' | 'fhir_pushed';

/** Sections of a SOAP note */
export type SOAPSectionType = 'subjective' | 'objective' | 'assessment' | 'plan';

/** An ICD-10 diagnosis code */
export interface ICDCode {
  code: string;
  description: string;
  confidence: number; // 0-1, AI confidence
  ai_suggested: boolean;
  category?: string;
}

/** A CPT procedure code */
export interface CPTCode {
  code: string;
  description: string;
  units: number;
  ai_suggested: boolean;
  modifier?: string;
}

/** A single section of a SOAP note */
export interface SOAPSection {
  type: SOAPSectionType;
  ai_generated_text: string;
  physician_edited_text: string | null; // null = not yet edited
  is_modified: boolean;
  last_modified_at: string | null;
  last_modified_by: string | null;
}

/** A complete SOAP note */
export interface SOAPNote {
  id: string;
  session_id: string;
  transcript_id: string;
  patient_mrn: string;
  patient_name: string;
  encounter_id: string;
  physician_id: string;
  status: NoteStatus;
  sections: {
    subjective: SOAPSection;
    objective: SOAPSection;
    assessment: SOAPSection;
    plan: SOAPSection;
  };
  icd_codes: ICDCode[];
  cpt_codes: CPTCode[];
  version: number;
  approved_at: string | null;
  approved_by: string | null;
  expires_at: string; // 24h after generation
  fhir_pushed_at: string | null;
  fhir_resource_id: string | null;
  created_at: string;
  updated_at: string;
}

/** Request to edit a SOAP note section */
export interface EditNoteRequest {
  section?: SOAPSectionType;
  text?: string;
  icd_codes?: ICDCode[];
  cpt_codes?: CPTCode[];
}

/** ICD-10 search result */
export interface ICDSearchResult {
  code: string;
  description: string;
  category: string;
  relevance_score: number;
}

/** Note history entry */
export interface NoteHistoryEntry {
  id: string;
  patient_name: string;
  patient_mrn: string;
  encounter_id: string;
  status: NoteStatus;
  physician_name: string;
  session_date: string;
  approved_at: string | null;
  expires_at: string;
  fhir_pushed_at: string | null;
}
