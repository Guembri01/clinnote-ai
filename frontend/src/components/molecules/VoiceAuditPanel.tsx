/**
 * VoiceAuditPanel — Phase D voice ↔ SOAP cross-validation UI for ClinNote AI
 *
 * Adds two action buttons to a SOAP note review surface:
 *  - Clinical QA Audit (POST /notes/{id}/voice-audit, JSON)
 *  - Clinical QA Brief PDF (GET /notes/{id}/clinical-qa-brief.pdf, blob)
 *
 * Audit summary surfaces:
 *  - decision
 *  - critical-unescalated count
 *  - missing allergy count
 *  - uncoded ICD count
 */

import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { downloadClinicalQABrief, runVoiceAudit, type VoiceAuditResult } from '@/api/notes';
import { Button } from '@/components/atoms/Button';
import { useToast } from '@/components/atoms/Toast';

export interface VoiceAuditPanelProps {
  noteId: string;
}

const decisionTone: Record<string, string> = {
  escalate: 'text-red-300 bg-red-900/30 border-red-700',
  review: 'text-amber-300 bg-amber-900/30 border-amber-700',
  ok: 'text-green-300 bg-green-900/30 border-green-700',
  pass: 'text-green-300 bg-green-900/30 border-green-700',
};

export const VoiceAuditPanel: React.FC<VoiceAuditPanelProps> = ({ noteId }) => {
  const { toast } = useToast();
  const [result, setResult] = useState<VoiceAuditResult | null>(null);

  const { mutate: audit, isPending: isAuditing } = useMutation({
    mutationFn: () => runVoiceAudit(noteId),
    onSuccess: (data) => {
      setResult(data);
      toast.success('Clinical QA audit complete.');
    },
    onError: () => {
      toast.error('Voice audit failed. Please try again.');
    },
  });

  const { mutate: downloadPdf, isPending: isDownloading } = useMutation({
    mutationFn: () => downloadClinicalQABrief(noteId),
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `clinical-qa-brief-${noteId}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      toast.success('Clinical QA brief downloaded.');
    },
    onError: () => {
      toast.error('Could not download brief PDF.');
    },
  });

  const decisionRaw = (result?.decision ?? '').toString().toLowerCase();
  const decisionClass = decisionTone[decisionRaw] ?? 'text-gray-200 bg-primary-800/50 border-primary-700';

  return (
    <div className="rounded-xl border border-primary-700 bg-primary-900/30 p-4 space-y-3">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h3 className="text-base font-semibold text-white">Voice ↔ SOAP Cross-Check</h3>
          <p className="text-xs text-gray-400 mt-0.5">
            Compare the dictated audio against the generated note for safety and coding gaps.
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Button
            variant="secondary"
            size="md"
            loading={isAuditing}
            onClick={() => audit()}
            aria-label="Run clinical QA voice audit"
          >
            {isAuditing ? 'Auditing...' : '🎙️ Clinical QA Audit'}
          </Button>
          <Button
            variant="ghost"
            size="md"
            loading={isDownloading}
            onClick={() => downloadPdf()}
            aria-label="Download clinical QA brief PDF"
          >
            {isDownloading ? 'Preparing...' : '📄 Clinical QA Brief PDF'}
          </Button>
        </div>
      </div>

      {result && (
        <div className={`rounded-lg border px-3 py-2 ${decisionClass}`}>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
            <span>
              <span className="text-gray-400">Decision:</span>{' '}
              <span className="font-semibold uppercase">{result.decision ?? '—'}</span>
            </span>
            <span>
              <span className="text-gray-400">Critical unescalated:</span>{' '}
              <span className="font-semibold">{result.critical_unescalated?.length ?? 0}</span>
            </span>
            <span>
              <span className="text-gray-400">Missing allergies:</span>{' '}
              <span className="font-semibold">{result.missing_allergies_in_note?.length ?? 0}</span>
            </span>
            <span>
              <span className="text-gray-400">Uncoded ICD:</span>{' '}
              <span className="font-semibold">{result.uncoded_icd?.length ?? 0}</span>
            </span>
          </div>
          {result.status === 'no_transcript' && (
            <p className="text-xs mt-1 text-gray-400">
              No voice transcript on file — audit ran in note-only mode.
            </p>
          )}
        </div>
      )}
    </div>
  );
};
