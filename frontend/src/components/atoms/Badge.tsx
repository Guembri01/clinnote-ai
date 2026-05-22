/**
 * Badge atom for ClinNote AI
 *
 * Status indicator badges with clinical color coding.
 *
 * @example
 * <Badge status="approved">Approved</Badge>
 * <Badge variant="info">ICD-10</Badge>
 */

import React from 'react';
import { clsx } from 'clsx';
import type { NoteStatus } from '@/types/soap';

export type BadgeVariant =
  | 'default'
  | 'info'
  | 'success'
  | 'warning'
  | 'danger'
  | 'muted'
  | 'teal';

export interface BadgeProps {
  /** Visual color variant */
  variant?: BadgeVariant;
  /** Map note status to appropriate color */
  status?: NoteStatus;
  /** Badge content */
  children?: React.ReactNode;
  /** Optional CSS classes */
  className?: string;
  /** Size variant */
  size?: 'sm' | 'md';
}

const variantClasses: Record<BadgeVariant, string> = {
  default: 'bg-gray-700 text-gray-200 border border-gray-600',
  info: 'bg-primary-800 text-primary-200 border border-primary-600',
  success: 'bg-green-900/60 text-green-300 border border-green-700',
  warning: 'bg-amber-900/60 text-amber-300 border border-amber-700',
  danger: 'bg-red-900/60 text-red-300 border border-red-700',
  muted: 'bg-gray-800 text-gray-400 border border-gray-700',
  teal: 'bg-teal-900/60 text-teal-300 border border-teal-700',
};

const statusToVariant: Record<NoteStatus, BadgeVariant> = {
  generating: 'info',
  draft: 'warning',
  approved: 'success',
  expired: 'danger',
  fhir_pushed: 'teal',
};

const statusLabels: Record<NoteStatus, string> = {
  generating: 'Generating...',
  draft: 'Draft',
  approved: 'Approved',
  expired: 'Expired',
  fhir_pushed: 'In EHR',
};

/** Status icons for colorblind accessibility */
const statusIcons: Record<NoteStatus, React.ReactNode> = {
  generating: (
    <svg className="h-3 w-3 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
    </svg>
  ),
  draft: (
    <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
    </svg>
  ),
  approved: (
    <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
    </svg>
  ),
  expired: (
    <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
  fhir_pushed: (
    <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
    </svg>
  ),
};

/**
 * Clinical Badge Component
 */
export const Badge: React.FC<BadgeProps> = ({
  variant,
  status,
  children,
  className,
  size = 'md',
}) => {
  const resolvedVariant = status ? statusToVariant[status] : (variant ?? 'default');
  const label = status && !children ? statusLabels[status] : children;

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full font-medium',
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-xs',
        variantClasses[resolvedVariant],
        className
      )}
    >
      {status && statusIcons[status]}
      {label}
    </span>
  );
};
