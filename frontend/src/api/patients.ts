/**
 * Patient API functions for ClinNote AI
 */

import apiClient from './client';
import type { PatientInfo } from '@/types/recording';

export interface Patient extends PatientInfo {
  id: string;
  created_at: string;
  updated_at: string;
}

/**
 * Create or register a new patient record
 */
export async function createPatient(patient: Omit<PatientInfo, 'encounter_id'>): Promise<Patient> {
  const { data } = await apiClient.post<Patient>('/patients', patient);
  return data;
}

/**
 * Get a patient by MRN
 */
export async function getPatient(mrn: string): Promise<Patient> {
  const { data } = await apiClient.get<Patient>(`/patients/${mrn}`);
  return data;
}

/**
 * Search patients by name or MRN
 */
export async function searchPatients(query: string): Promise<Patient[]> {
  const { data } = await apiClient.get<Patient[]>('/patients/search', {
    params: { q: query },
  });
  return data;
}
