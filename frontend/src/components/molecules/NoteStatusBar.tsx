/**
 * NoteStatusBar molecule for ClinNote AI
 *
 * Shows note status badge and expiry countdown.
 * Amber warning when within 2 hours of 24h expiry.
 *
 * @example
 * <NoteStatusBar note={soapNote} />
 */

import React, { useEffect, useState } from 'react';
import { clsx } from 'clsx';
import type { SOAPNote } from '@/types/soap';
import { Badge } from '@/components/atoms/Badge';
import { getSecondsUntilExpiry } from '@/utils/formatters';

export interface NoteStatusBarProps {
  note: SOAPNote;
  className?: string;
}

/**
 * Note Status and Expiry Bar
 */
export const NoteStatusBar: React.FC<NoteStatusBarProps> = ({ note, className }) => {
  const [secondsUntilExpiry, setSecondsUntilExpiry] = useState(() =>
    getSecondsUntilExpiry(note.expires_at)
  );

  useEffect(() => {
    const interval = setInterval(() => {
      setSecondsUntilExpiry(getSecondsUntilExpiry(note.expires_at));
    }, 1000);
    return () => clearInterval(interval);
  }, [note.expires_at]);

  const isExpired = secondsUntilExpiry <= 0;
  const isWarning = secondsUntilExpiry > 0 && secondsUntilExpiry <= 2 * 60 * 60; // 2h warning
  const hoursRemaining = Math.floor(secondsUntilExpiry / 3600);
  const minutesRemaining = Math.floor((secondsUntilExpiry % 3600) / 60);

  if (note.status === 'approved' || note.status === 'fhir_pushed') {
    return (
      <div
        className={clsx(
          'flex items-center gap-3 px-4 py-2.5 rounded-lg',
          'bg-green-900/20 border border-green-800/40',
          className
        )}
      >
        <Badge status={note.status} />
        {note.approved_at && (
          <span className="text-xs text-gray-400">
            Approved {new Date(note.approved_at).toLocaleDateString()}
          </span>
        )}
        {note.status === 'fhir_pushed' && note.fhir_pushed_at && (
          <div className="flex items-center gap-1.5 ml-auto">
            <svg className="h-4 w-4 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-xs text-teal-400 font-medium">Pushed to EHR</span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={`Note status: ${note.status}. ${isExpired ? 'Expired' : `Expires in ${hoursRemaining}h ${minutesRemaining}m`}`}
      className={clsx(
        'flex items-center justify-between gap-3 px-4 py-2.5 rounded-lg border',
        isExpired
          ? 'bg-red-900/20 border-red-800/40'
          : isWarning
          ? 'bg-amber-900/20 border-amber-700/40'
          : 'bg-primary-800/30 border-primary-700',
        className
      )}
    >
      <div className="flex items-center gap-3">
        <Badge status={note.status} />
        <span className="text-sm text-gray-300">
          Note v{note.version ?? 1}
        </span>
      </div>

      <div className="flex items-center gap-2">
        {isExpired ? (
          <div className="flex items-center gap-1.5">
            <svg className="h-4 w-4 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-xs font-medium text-red-400">Expired</span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5">
            <svg
              className={clsx('h-4 w-4', isWarning ? 'text-amber-400' : 'text-gray-400')}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className={clsx('text-xs font-medium', isWarning ? 'text-amber-400' : 'text-gray-400')}>
              {isWarning
                ? `Expires in ${hoursRemaining}h ${minutesRemaining}m`
                : `${hoursRemaining}h ${minutesRemaining}m remaining`}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
