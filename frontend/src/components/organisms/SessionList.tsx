/**
 * SessionList organism for ClinNote AI
 *
 * Paginated list of past recording sessions with status badges.
 *
 * @example
 * <SessionList />
 */

import React from 'react';
import { clsx } from 'clsx';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getNotesHistory } from '@/api/notes';
import { Badge } from '@/components/atoms/Badge';
import { Button } from '@/components/atoms/Button';
import type { NoteHistoryEntry } from '@/types/soap';
import { formatDate, formatMRN } from '@/utils/formatters';

export interface SessionListProps {
  limit?: number;
  showPagination?: boolean;
  status?: string;
  search?: string;
}

/**
 * Past Sessions List
 */
export const SessionList: React.FC<SessionListProps> = ({
  limit = 10,
  showPagination = true,
  status,
  search,
}) => {
  const [page, setPage] = React.useState(1);

  // Reset to page 1 whenever filters change
  React.useEffect(() => { setPage(1); }, [status, search]);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['notes-history', page, limit, status, search],
    queryFn: () => getNotesHistory({ page, page_size: limit, status: status || undefined, search: search || undefined }),
  });

  if (isLoading) return <SessionListSkeleton />;

  if (isError) {
    return (
      <div role="alert" className="rounded-xl border border-red-700 bg-red-900/20 p-6 text-center">
        <p className="text-red-300 font-medium">Failed to load sessions</p>
        <p className="text-red-400 text-sm mt-1">{(error as Error).message}</p>
      </div>
    );
  }

  const notes = data?.data ?? [];

  if (notes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
        <svg className="h-12 w-12 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <div>
          <p className="text-gray-300 font-medium">No sessions yet</p>
          <p className="text-gray-500 text-sm mt-1">Start a new recording session to generate your first note</p>
        </div>
        <Link to="/sessions/new">
          <Button variant="primary" size="lg">
            New Session
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* List */}
      <div className="divide-y divide-primary-800 rounded-xl border border-primary-700 overflow-hidden">
        {notes.map((note) => (
          <SessionRow key={note.id} note={note} />
        ))}
      </div>

      {/* Pagination */}
      {showPagination && data && data.total_pages > 1 && (
        <div className="flex items-center justify-between px-1">
          <p className="text-sm text-gray-400">
            {data.total} total notes
          </p>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="md"
              disabled={!data.has_prev}
              onClick={() => setPage((p) => p - 1)}
              aria-label="Previous page"
            >
              Previous
            </Button>
            <span className="flex items-center px-3 text-sm text-gray-400">
              Page {page} of {data.total_pages}
            </span>
            <Button
              variant="ghost"
              size="md"
              disabled={!data.has_next}
              onClick={() => setPage((p) => p + 1)}
              aria-label="Next page"
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

/** Skeleton loader for session list */
const SessionListSkeleton: React.FC = () => (
  <div className="divide-y divide-primary-800 rounded-xl border border-primary-700 overflow-hidden" aria-busy="true" aria-label="Loading sessions...">
    {Array.from({ length: 4 }).map((_, i) => (
      <div key={i} className="flex items-center gap-4 px-4 py-4 bg-primary-900/30">
        <div className="flex-1 space-y-2">
          <div className="skeleton h-4 w-40" />
          <div className="skeleton h-3 w-56" />
        </div>
        <div className="skeleton h-6 w-16 rounded-full" />
      </div>
    ))}
  </div>
);

const SessionRow: React.FC<{ note: NoteHistoryEntry }> = ({ note }) => (
  <Link
    to={`/notes/${note.id}/review`}
    className={clsx(
      'flex items-center gap-4 px-4 py-4',
      'bg-primary-900/30 hover:bg-primary-800/50 transition-colors',
      'focus:outline-none focus:ring-2 focus:ring-inset focus:ring-teal-500'
    )}
    aria-label={`Review note for ${note.patient_name}`}
  >
    {/* Patient info */}
    <div className="flex-1 min-w-0">
      <div className="flex items-center gap-2">
        <p className="text-sm font-semibold text-gray-100 truncate">{note.patient_name}</p>
        <span className="text-xs text-gray-500 font-mono">{formatMRN(note.patient_mrn)}</span>
      </div>
      <p className="text-xs text-gray-400 mt-0.5">
        {formatDate(note.session_date)} · {note.physician_name}
      </p>
    </div>

    {/* Status */}
    <div className="flex items-center gap-3 shrink-0">
      <Badge status={note.status} />
      {note.fhir_pushed_at && (
        <svg className="h-4 w-4 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <title>Pushed to EHR</title>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      )}
    </div>

    <svg className="h-4 w-4 text-gray-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
    </svg>
  </Link>
);
