/**
 * Spinner atom for ClinNote AI
 *
 * Loading spinner with size variants.
 *
 * @example
 * <Spinner size="lg" label="Loading note..." />
 */

import React from 'react';
import { clsx } from 'clsx';

export type SpinnerSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

export interface SpinnerProps {
  /** Size of the spinner */
  size?: SpinnerSize;
  /** Accessible label for screen readers */
  label?: string;
  /** Optional CSS classes */
  className?: string;
  /** Color class — defaults to teal */
  color?: string;
}

const sizeClasses: Record<SpinnerSize, string> = {
  xs: 'h-3 w-3 border',
  sm: 'h-4 w-4 border-2',
  md: 'h-6 w-6 border-2',
  lg: 'h-8 w-8 border-[3px]',
  xl: 'h-12 w-12 border-4',
};

/**
 * Clinical Loading Spinner
 */
export const Spinner: React.FC<SpinnerProps> = ({
  size = 'md',
  label = 'Loading...',
  className,
  color = 'border-teal-400',
}) => {
  return (
    <span
      role="status"
      aria-label={label}
      className={clsx('inline-block', className)}
    >
      <span
        className={clsx(
          'block rounded-full animate-spin',
          'border-transparent',
          color,
          sizeClasses[size]
        )}
        style={{ borderTopColor: 'currentColor' }}
      />
      <span className="sr-only">{label}</span>
    </span>
  );
};

/** Full-page loading overlay */
export const LoadingOverlay: React.FC<{ label?: string }> = ({ label = 'Loading...' }) => (
  <div
    role="status"
    aria-live="polite"
    className="flex flex-col items-center justify-center gap-4 py-20"
  >
    <Spinner size="xl" label={label} />
    <p className="text-gray-400 text-sm">{label}</p>
  </div>
);
