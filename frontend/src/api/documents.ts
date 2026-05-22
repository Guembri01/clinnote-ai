/**
 * Document upload API for ClinNote AI
 */

import apiClient from './client';

export interface UploadedDocument {
  id: string;
  filename: string;
  file_type: string;
  size_bytes: number;
  uploaded_at: string;
  url: string;
}

/**
 * Upload a lab report or clinical document (PDF or image)
 * @param file - The file to upload
 * @param onProgress - Optional upload progress callback (0-100)
 */
export async function uploadDocument(
  file: File,
  onProgress?: (progress: number) => void
): Promise<UploadedDocument> {
  const formData = new FormData();
  formData.append('file', file);

  const { data } = await apiClient.post<UploadedDocument>('/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (progressEvent) => {
      if (onProgress && progressEvent.total) {
        const pct = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        onProgress(pct);
      }
    },
  });

  return data;
}

/**
 * Delete an uploaded document
 */
export async function deleteDocument(documentId: string): Promise<void> {
  await apiClient.delete(`/documents/${documentId}`);
}
