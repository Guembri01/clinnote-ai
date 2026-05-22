/**
 * ICD-10 code search API for ClinNote AI
 */

import apiClient from './client';
import type { ICDSearchResult } from '@/types/soap';

/**
 * Search ICD-10 codes by description or code number
 * @param query - Search term (e.g., "hypertension" or "I10")
 * @param limit - Maximum results to return (default 20)
 */
export async function searchICD(query: string, limit = 20): Promise<ICDSearchResult[]> {
  const { data } = await apiClient.get<ICDSearchResult[]>('/icd/search', {
    params: { q: query, limit },
  });
  return data;
}

/**
 * Get details for a specific ICD-10 code
 */
export async function getICDCode(code: string): Promise<ICDSearchResult> {
  const { data } = await apiClient.get<ICDSearchResult>(`/icd/${code}`);
  return data;
}
