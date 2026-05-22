/**
 * Formatting utilities for ClinNote AI
 */

import { format, formatDistanceToNow, differenceInSeconds, parseISO } from 'date-fns';

/**
 * Format duration in seconds to MM:SS display string
 * @example formatDuration(75) → "01:15"
 */
export function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

/**
 * Format duration in seconds to HH:MM:SS (for longer recordings)
 * @example formatDurationLong(3725) → "01:02:05"
 */
export function formatDurationLong(seconds: number): string {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  if (hrs > 0) {
    return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }
  return formatDuration(seconds);
}

/**
 * Format a date/ISO string in clinical format
 * @example formatDate("2024-01-15T14:30:00Z") → "Jan 15, 2024 at 2:30 PM"
 */
export function formatDate(dateStr: string): string {
  return format(parseISO(dateStr), "MMM d, yyyy 'at' h:mm a");
}

/**
 * Format a date to short form
 * @example formatDateShort("2024-01-15") → "01/15/2024"
 */
export function formatDateShort(dateStr: string): string {
  return format(parseISO(dateStr), 'MM/dd/yyyy');
}

/**
 * Format relative time (e.g. "2 minutes ago")
 */
export function formatRelativeTime(dateStr: string): string {
  return formatDistanceToNow(parseISO(dateStr), { addSuffix: true });
}

/**
 * Format a Medical Record Number with dashes
 * @example formatMRN("123456789") → "123-456-789"
 */
export function formatMRN(mrn: string): string {
  const clean = mrn.replace(/\D/g, '');
  if (clean.length === 9) {
    return `${clean.slice(0, 3)}-${clean.slice(3, 6)}-${clean.slice(6)}`;
  }
  return mrn;
}

/**
 * Format a date of birth
 * @example formatDOB("1980-05-20") → "05/20/1980"
 */
export function formatDOB(dob: string): string {
  return format(parseISO(dob), 'MM/dd/yyyy');
}

/**
 * Calculate seconds remaining until expiry
 */
export function getSecondsUntilExpiry(expiresAt: string): number {
  return Math.max(0, differenceInSeconds(parseISO(expiresAt), new Date()));
}

/**
 * Format file size for display
 * @example formatFileSize(1536) → "1.5 KB"
 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Get patient full name from first/last
 */
export function formatPatientName(firstName: string, lastName: string): string {
  return `${lastName}, ${firstName}`;
}

/**
 * Format confidence score as a percentage
 * @example formatConfidence(0.923) → "92%"
 */
export function formatConfidence(score: number): string {
  return `${Math.round(score * 100)}%`;
}

/**
 * Format seconds to "Xm Xs" display
 * @example formatDurationVerbose(125) → "2m 5s"
 */
export function formatDurationVerbose(seconds: number): string {
  if (seconds < 10) return 'Just started';
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins === 0) return `${secs}s`;
  if (secs === 0) return `${mins}m`;
  return `${mins}m ${secs}s`;
}
