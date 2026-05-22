/**
 * InactivityWarning molecule for ClinNote AI
 *
 * HIPAA inactivity warning modal shown at 14 minutes of inactivity.
 * Forces logout at 15 minutes to protect PHI.
 *
 * @example
 * <InactivityWarning
 *   isOpen={showWarning}
 *   secondsRemaining={45}
 *   onDismiss={dismissWarning}
 * />
 */

import React from 'react';
import { clsx } from 'clsx';
import { Button } from '@/components/atoms/Button';
import { useEscapeKey } from '@/hooks/useEscapeKey';

export interface InactivityWarningProps {
  isOpen: boolean;
  secondsRemaining: number;
  onDismiss: () => void;
}

/**
 * HIPAA Session Inactivity Warning
 */
export const InactivityWarning: React.FC<InactivityWarningProps> = ({
  isOpen,
  secondsRemaining,
  onDismiss,
}) => {
  // Escape = "Continue session" — keep the physician's session alive.
  useEscapeKey(onDismiss, isOpen);

  if (!isOpen) return null;

  const isUrgent = secondsRemaining <= 30;

  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="inactivity-title"
      aria-describedby="inactivity-desc"
      aria-live="assertive"
      className="fixed inset-0 z-[60] flex items-center justify-center p-4"
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" aria-hidden="true" />

      {/* Modal */}
      <div
        className={clsx(
          'relative w-full max-w-sm rounded-2xl shadow-2xl border animate-slide-in-up',
          isUrgent
            ? 'bg-red-950 border-red-700'
            : 'bg-primary-900 border-amber-700/60'
        )}
      >
        {/* Warning icon */}
        <div className="p-6 pb-0 flex flex-col items-center text-center">
          <div
            className={clsx(
              'flex h-16 w-16 items-center justify-center rounded-full mb-4',
              isUrgent ? 'bg-red-900' : 'bg-amber-900/50'
            )}
          >
            <svg
              className={clsx('h-8 w-8', isUrgent ? 'text-red-400' : 'text-amber-400')}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>

          <h2 id="inactivity-title" className="text-lg font-bold text-white mb-2">
            Session Expiring
          </h2>

          <p id="inactivity-desc" className="text-sm text-gray-300 mb-4">
            For HIPAA compliance, your session will automatically end due to inactivity.
            Any unsaved work will be preserved as a draft.
          </p>

          {/* Countdown */}
          <div
            className={clsx(
              'flex items-center justify-center h-20 w-20 rounded-full border-4 mb-4',
              isUrgent
                ? 'border-red-500 text-red-300'
                : 'border-amber-500 text-amber-300'
            )}
            aria-label={`${secondsRemaining} seconds remaining`}
          >
            <span className="text-2xl font-bold font-mono tabular-nums">
              {secondsRemaining}
            </span>
          </div>

          <p className="text-xs text-gray-400 mb-6">seconds until automatic logout</p>
        </div>

        <div className="px-6 pb-6">
          <Button
            variant={isUrgent ? 'danger' : 'warning'}
            size="lg"
            fullWidth
            onClick={onDismiss}
            aria-label="Continue session"
          >
            Continue Session
          </Button>
        </div>
      </div>
    </div>
  );
};
