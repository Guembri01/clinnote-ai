/**
 * LabReportUpload molecule for ClinNote AI
 *
 * Drag-and-drop file upload for lab reports (PDF and images).
 *
 * @example
 * <LabReportUpload
 *   onUpload={(docId) => addLabDocument(docId)}
 *   maxFiles={5}
 * />
 */

import React, { useState, useRef, useCallback } from 'react';
import { clsx } from 'clsx';
import { uploadDocument } from '@/api/documents';
import type { UploadedDocument } from '@/api/documents';
import { formatFileSize } from '@/utils/formatters';
import { Button } from '@/components/atoms/Button';

export interface LabReportUploadProps {
  /** Called when a document is successfully uploaded */
  onUpload: (doc: UploadedDocument) => void;
  /** Called when a document is removed */
  onRemove?: (docId: string) => void;
  /** Maximum number of files allowed */
  maxFiles?: number;
  /** Already uploaded documents */
  uploadedDocuments?: UploadedDocument[];
}

interface UploadingFile {
  id: string;
  name: string;
  size: number;
  progress: number;
  error?: string;
}

const ACCEPTED_TYPES = ['application/pdf', 'image/png', 'image/jpeg', 'image/jpg', 'image/tiff'];
const MAX_FILE_SIZE_MB = 50;

/**
 * Lab Report File Upload
 */
export const LabReportUpload: React.FC<LabReportUploadProps> = ({
  onUpload,
  onRemove,
  maxFiles = 5,
  uploadedDocuments = [],
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [uploadingFiles, setUploadingFiles] = useState<UploadingFile[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const processFiles = useCallback(
    async (files: File[]) => {
      const remaining = maxFiles - uploadedDocuments.length;
      const toProcess = files.slice(0, remaining);

      for (const file of toProcess) {
        // Validate type
        if (!ACCEPTED_TYPES.includes(file.type)) {
          setUploadingFiles((prev) => [
            ...prev,
            { id: file.name, name: file.name, size: file.size, progress: 0, error: 'Invalid file type' },
          ]);
          continue;
        }

        // Validate size
        if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
          setUploadingFiles((prev) => [
            ...prev,
            { id: file.name, name: file.name, size: file.size, progress: 0, error: `File too large (max ${MAX_FILE_SIZE_MB}MB)` },
          ]);
          continue;
        }

        const tempId = `upload-${Date.now()}-${file.name}`;
        setUploadingFiles((prev) => [
          ...prev,
          { id: tempId, name: file.name, size: file.size, progress: 0 },
        ]);

        try {
          const doc = await uploadDocument(file, (progress) => {
            setUploadingFiles((prev) =>
              prev.map((f) => (f.id === tempId ? { ...f, progress } : f))
            );
          });
          onUpload(doc);
          setUploadingFiles((prev) => prev.filter((f) => f.id !== tempId));
        } catch {
          setUploadingFiles((prev) =>
            prev.map((f) =>
              f.id === tempId ? { ...f, error: 'Upload failed. Please try again.' } : f
            )
          );
        }
      }
    },
    [maxFiles, uploadedDocuments.length, onUpload]
  );

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files);
    processFiles(files);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    processFiles(files);
    e.target.value = '';
  };

  const canUploadMore = uploadedDocuments.length + uploadingFiles.filter((f) => !f.error).length < maxFiles;

  return (
    <div className="space-y-3">
      {/* Drop zone */}
      {canUploadMore && (
        <div
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          role="region"
          aria-label="File upload area"
          className={clsx(
            'relative flex flex-col items-center justify-center gap-3',
            'rounded-xl border-2 border-dashed p-8 text-center',
            'transition-all duration-200 cursor-pointer',
            isDragging
              ? 'border-teal-500 bg-teal-900/10'
              : 'border-primary-600 hover:border-primary-500 hover:bg-primary-800/20'
          )}
          onClick={() => fileInputRef.current?.click()}
          onKeyDown={(e) => e.key === 'Enter' && fileInputRef.current?.click()}
          tabIndex={0}
        >
          <svg
            className={clsx('h-10 w-10', isDragging ? 'text-teal-400' : 'text-gray-500')}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>

          <div>
            <p className="text-sm font-medium text-gray-300">
              Drop lab reports here, or{' '}
              <span className="text-teal-400 underline">browse files</span>
            </p>
            <p className="text-xs text-gray-500 mt-1">
              PDF, PNG, JPG, TIFF — up to {MAX_FILE_SIZE_MB}MB each
            </p>
            <p className="text-xs text-gray-500">
              Up to {maxFiles} files total
            </p>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={ACCEPTED_TYPES.join(',')}
            onChange={handleFileInput}
            className="sr-only"
            aria-label="Upload lab reports"
          />
        </div>
      )}

      {/* Uploading files */}
      {uploadingFiles.map((file) => (
        <div
          key={file.id}
          className="flex items-center gap-3 rounded-lg bg-primary-800/50 border border-primary-700 px-4 py-3"
        >
          <svg className="h-5 w-5 text-gray-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>

          <div className="flex-1 min-w-0">
            <p className="text-sm text-gray-200 truncate">{file.name}</p>
            {file.error ? (
              <p className="text-xs text-red-400">{file.error}</p>
            ) : (
              <div className="mt-1 h-1.5 rounded-full bg-primary-700 overflow-hidden">
                <div
                  className="h-full bg-teal-500 transition-all duration-300 rounded-full"
                  style={{ width: `${file.progress}%` }}
                  role="progressbar"
                  aria-valuenow={file.progress}
                  aria-valuemin={0}
                  aria-valuemax={100}
                />
              </div>
            )}
          </div>

          <span className="text-xs text-gray-500 shrink-0">{formatFileSize(file.size)}</span>

          {file.error && (
            <button
              onClick={() => setUploadingFiles((prev) => prev.filter((f) => f.id !== file.id))}
              aria-label="Dismiss error"
              className="text-gray-500 hover:text-gray-300 min-h-[32px] min-w-[32px] flex items-center justify-center"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      ))}

      {/* Uploaded documents */}
      {uploadedDocuments.map((doc) => (
        <div
          key={doc.id}
          className="flex items-center gap-3 rounded-lg bg-primary-800/50 border border-green-800/40 px-4 py-3"
        >
          <svg className="h-5 w-5 text-green-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>

          <div className="flex-1 min-w-0">
            <p className="text-sm text-gray-200 truncate">{doc.filename}</p>
            <p className="text-xs text-gray-500">{formatFileSize(doc.size_bytes)}</p>
          </div>

          {onRemove && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onRemove(doc.id)}
              aria-label={`Remove ${doc.filename}`}
            >
              Remove
            </Button>
          )}
        </div>
      ))}
    </div>
  );
};
