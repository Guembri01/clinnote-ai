/**
 * NotesHistoryPage for ClinNote AI
 *
 * Paginated list of all notes with search and filter.
 */

import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { SessionList } from '@/components/organisms/SessionList';
import { Input } from '@/components/atoms/Input';

const STATUS_OPTIONS: Array<{ value: string; label: string }> = [
  { value: '', label: 'All Statuses' },
  { value: 'draft', label: 'Draft' },
  { value: 'approved', label: 'Approved' },
  { value: 'expired', label: 'Expired' },
  { value: 'fhir_pushed', label: 'In EHR' },
];

/**
 * Notes History Page
 */
export const NotesHistoryPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState(searchParams.get('search') ?? '');
  const [status, setStatus] = useState<string>(searchParams.get('status') ?? '');

  const updateFilters = (newSearch?: string, newStatus?: string) => {
    const params = new URLSearchParams();
    const s = newSearch ?? search;
    const st = newStatus ?? status;
    if (s) params.set('search', s);
    if (st) params.set('status', st);
    setSearchParams(params);
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Notes History</h1>
        <p className="text-gray-400 text-sm mt-1">All clinical notes from recording sessions</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex-1 min-w-60">
          <Input
            placeholder="Search by patient name or MRN..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              updateFilters(e.target.value, undefined);
            }}
            aria-label="Search notes"
            leftIcon={
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            }
          />
        </div>

        {/* Status filter */}
        <div className="flex gap-1">
          {STATUS_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => {
                setStatus(opt.value);
                updateFilters(undefined, opt.value);
              }}
              aria-pressed={status === opt.value}
              className={`px-3 py-2 rounded-lg text-xs font-medium transition-colors min-h-[44px] ${
                status === opt.value
                  ? 'bg-primary-600 text-white border border-primary-500'
                  : 'text-gray-400 hover:text-white hover:bg-primary-800 border border-transparent'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Notes list */}
      <SessionList limit={20} showPagination status={status} search={search} />
    </div>
  );
};
