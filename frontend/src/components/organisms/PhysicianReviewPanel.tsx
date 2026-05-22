/**
 * PhysicianReviewPanel organism for ClinNote AI
 *
 * Review interface with approve, FHIR push, and edit action buttons.
 *
 * @example
 * <PhysicianReviewPanel note={soapNote} onApproved={() => refetch()} />
 */

import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { approveNote, pushToFHIR } from '@/api/notes';
import { useNoteEditor } from '@/hooks/useNoteEditor';
import { SOAPNoteEditor } from './SOAPNoteEditor';
import { Button } from '@/components/atoms/Button';
import { useToast } from '@/components/atoms/Toast';
import type { SOAPNote } from '@/types/soap';
import { formatDate } from '@/utils/formatters';

export interface PhysicianReviewPanelProps {
  note: SOAPNote;
  onApproved?: (note: SOAPNote) => void;
}

/**
 * Physician Review and Approval Panel
 */
export const PhysicianReviewPanel: React.FC<PhysicianReviewPanelProps> = ({
  note,
  onApproved,
}) => {
  const queryClient = useQueryClient();
  const [showConfirmApprove, setShowConfirmApprove] = useState(false);
  const { saveNote, hasUnsavedChanges } = useNoteEditor(note.id);
  const { toast } = useToast();

  const { mutate: approve, isPending: isApproving, error: approveError } = useMutation({
    mutationFn: () => approveNote(note.id),
    onSuccess: (updated) => {
      queryClient.setQueryData(['note', note.id], updated);
      onApproved?.(updated);
      setShowConfirmApprove(false);
      toast.success('Note signed and approved. It is now part of the patient\'s medical record.');
    },
    onError: () => {
      toast.error('Failed to approve note. Please try again.');
    },
  });

  const { mutate: pushFHIR, isPending: isPushing, error: fhirError } = useMutation({
    mutationFn: () => pushToFHIR(note.id),
    onSuccess: (updated) => {
      queryClient.setQueryData(['note', note.id], updated);
      toast.success('Note successfully sent to EHR.');
    },
    onError: () => {
      toast.error('EHR push failed. Please check your connection and retry.');
    },
  });

  const isApproved = note.status === 'approved' || note.status === 'fhir_pushed';
  const isFHIRPushed = note.status === 'fhir_pushed';
  const isExpired = note.status === 'expired';
  const canApprove = note.status === 'draft' && !isExpired;
  const canPushFHIR = note.status === 'approved' && !isFHIRPushed;

  const handleApprove = async () => {
    if (hasUnsavedChanges) {
      await saveNote();
    }
    approve();
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Action bar */}
      <div className="flex items-center justify-between gap-4 p-4 rounded-xl bg-primary-800/50 border border-primary-700">
        <div className="flex items-center gap-3">
          {/* FHIR push status */}
          {isFHIRPushed ? (
            <div className="flex items-center gap-2 text-teal-400">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-sm font-medium">Pushed to EHR</span>
              {note.fhir_pushed_at && (
                <span className="text-xs text-gray-400">{formatDate(note.fhir_pushed_at)}</span>
              )}
            </div>
          ) : fhirError ? (
            <div className="flex items-center gap-2">
              <svg className="h-5 w-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-sm text-red-400">FHIR push failed</span>
              <Button variant="secondary" size="sm" onClick={() => pushFHIR()}>
                Retry
              </Button>
            </div>
          ) : null}
        </div>

        <div className="flex items-center gap-3">
          {/* FHIR push button */}
          {canPushFHIR && (
            <Button
              variant="secondary"
              size="lg"
              loading={isPushing}
              onClick={() => pushFHIR()}
              aria-label="Send note to EHR"
              leftIcon={
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              }
            >
              {isPushing ? 'Sending to EHR...' : 'Send to EHR'}
            </Button>
          )}

          {/* Approve / Sign button */}
          {canApprove && !showConfirmApprove && (
            <Button
              variant="success"
              size="xl"
              onClick={() => setShowConfirmApprove(true)}
              aria-label="Sign and approve SOAP note (Ctrl+Enter)"
              leftIcon={
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
              }
            >
              Sign Note
            </Button>
          )}

          {/* Confirm sign */}
          {showConfirmApprove && (
            <div className="flex flex-col gap-2 bg-green-900/20 border border-green-700 rounded-lg px-4 py-3 max-w-sm">
              <p className="text-sm font-semibold text-green-300">Sign this note?</p>
              <p className="text-xs text-green-400/80">
                This action cannot be undone. The note will become part of the patient's legal medical record.
              </p>
              <div className="flex gap-2 mt-1">
                <Button variant="success" size="md" loading={isApproving} onClick={handleApprove}>
                  Yes, Sign Note
                </Button>
                <Button variant="ghost" size="md" onClick={() => setShowConfirmApprove(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          )}

          {/* Approved state */}
          {isApproved && !isFHIRPushed && (
            <div className="flex items-center gap-2 text-green-400">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-sm font-medium">Approved</span>
              {note.approved_at && (
                <span className="text-xs text-gray-400">{formatDate(note.approved_at)}</span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Error messages */}
      {approveError && (
        <div role="alert" className="rounded-lg bg-red-900/30 border border-red-700 p-3">
          <p className="text-sm text-red-300">{(approveError as Error).message}</p>
        </div>
      )}

      {/* SOAP Note Editor */}
      <SOAPNoteEditor note={note} readOnly={isApproved || isExpired} />
    </div>
  );
};
