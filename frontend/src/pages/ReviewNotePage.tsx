/**
 * ReviewNotePage for ClinNote AI
 *
 * Full SOAP note review, edit, approve, and FHIR push workflow.
 * Shows expiry countdown and edit history toggle.
 */

import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getNote, getNoteTranscript } from '@/api/notes';
import { useNoteStore } from '@/store/noteStore';
import { PhysicianReviewPanel } from '@/components/organisms/PhysicianReviewPanel';
import { VoiceAuditPanel } from '@/components/molecules/VoiceAuditPanel';
import { Button } from '@/components/atoms/Button';
import { formatMRN } from '@/utils/formatters';

/**
 * Review Note Page
 */
export const ReviewNotePage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { setCurrentNote } = useNoteStore();

  const { data: note, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['note', id],
    queryFn: () => getNote(id!),
    enabled: !!id,
  });

  // Phase E — fetch the persisted voice transcript (silent 404 if not transcribed yet)
  const { data: transcripts } = useQuery({
    queryKey: ['note-transcript', id],
    queryFn: () => getNoteTranscript(id!),
    enabled: !!id,
    retry: false,
  });

  // Sync note to store when loaded
  React.useEffect(() => {
    if (note) setCurrentNote(note);
  }, [note, setCurrentNote]);

  if (isLoading) return (
    <div className="space-y-6 animate-fade-in" aria-busy="true" aria-label="Loading note...">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="skeleton h-8 w-48" />
          <div className="skeleton h-4 w-72" />
        </div>
      </div>
      <div className="rounded-xl border border-primary-700 bg-primary-900/30 p-6 space-y-4">
        <div className="skeleton h-10 w-full rounded-lg" />
        {['S', 'O', 'A', 'P'].map((s) => (
          <div key={s} className="rounded-xl border border-primary-700 overflow-hidden">
            <div className="px-4 py-3 bg-primary-800/50">
              <div className="skeleton h-5 w-32" />
            </div>
            <div className="p-4 space-y-2">
              <div className="skeleton h-4 w-full" />
              <div className="skeleton h-4 w-4/5" />
              <div className="skeleton h-4 w-3/5" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  if (isError || !note) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
        <svg className="h-12 w-12 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <div>
          <h2 className="text-xl font-semibold text-white">Note Not Found</h2>
          <p className="text-gray-400 text-sm mt-1">
            {(error as Error)?.message ?? 'This note could not be loaded'}
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="ghost" size="lg" onClick={() => refetch()}>
            Retry
          </Button>
          <Button variant="primary" size="lg" onClick={() => navigate('/notes')}>
            View All Notes
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <button
              onClick={() => navigate(-1)}
              className="text-gray-400 hover:text-white transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg hover:bg-primary-800"
              aria-label="Go back"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <h1 className="text-2xl font-bold text-white">Review Note</h1>
          </div>
          <div className="flex flex-col gap-1 ml-11 tablet:flex-row tablet:items-baseline tablet:gap-4">
            <span className="font-semibold text-gray-200">{note.patient_name}</span>
            <div className="flex flex-wrap gap-x-4 text-sm text-gray-400">
              <span>MRN: {formatMRN(note.patient_mrn)}</span>
              <span>Encounter: {note.encounter_id}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Phase E — Voice Transcript Viewer */}
      {transcripts && transcripts.length > 0 && (
        <section
          className="rounded-xl border border-primary-700 bg-primary-900/30 p-4 space-y-3"
          aria-label="Voice transcript"
        >
          <div>
            <h3 className="text-base font-semibold text-white">🎙️ Voice Transcript</h3>
            <p className="text-xs text-gray-400 mt-0.5">
              The dictated audio that was transcribed for this note (decrypted on read).
            </p>
          </div>
          {transcripts.slice(0, 1).map((t) => (
            <div
              key={t.id}
              className="rounded-lg border border-primary-700 bg-primary-900/50 p-3"
            >
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-gray-400 mb-2">
                {t.provider && <span>provider: {t.provider}</span>}
                {t.language && <span>lang: {t.language.toUpperCase()}</span>}
                {t.confidence != null && (
                  <span>confidence: {(t.confidence * 100).toFixed(0)}%</span>
                )}
                {t.word_count != null && <span>{t.word_count} words</span>}
                <span className="ml-auto">
                  status: <span className="font-medium text-gray-300">{t.transcript_status}</span>
                  {t.created_at && (
                    <> · {new Date(t.created_at).toLocaleString()}</>
                  )}
                </span>
              </div>
              {t.voice_transcript ? (
                <pre className="whitespace-pre-wrap text-sm text-gray-200 font-sans leading-relaxed max-h-80 overflow-y-auto">
                  {t.voice_transcript}
                </pre>
              ) : (
                <p className="text-xs italic text-gray-500">
                  Transcript empty — transcription may still be in progress.
                </p>
              )}
            </div>
          ))}
        </section>
      )}

      {/* Phase D — Voice ↔ SOAP cross-validation */}
      <VoiceAuditPanel noteId={note.id} />

      {/* Review panel */}
      <PhysicianReviewPanel
        note={note}
        onApproved={(updated) => {
          setCurrentNote(updated);
        }}
      />
    </div>
  );
};
