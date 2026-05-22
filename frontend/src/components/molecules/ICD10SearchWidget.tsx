/**
 * ICD10SearchWidget molecule for ClinNote AI
 *
 * Search-as-you-type ICD-10 code picker with confidence pills + AI
 * reasoning drawer. Clicking a selected code opens the drawer.
 *
 * @example
 * <ICD10SearchWidget
 *   codes={note.icd_codes}
 *   onChange={updateICDCodes}
 * />
 */

import React, { useState, useRef, useEffect } from 'react';
import { clsx } from 'clsx';
import { useQuery } from '@tanstack/react-query';
import { searchICD } from '@/api/icd';
import type { ICDCode, ICDSearchResult } from '@/types/soap';
import { Badge } from '@/components/atoms/Badge';
import { Spinner } from '@/components/atoms/Spinner';
import { ConfidencePill } from '@/components/atoms/ConfidencePill';
import { useICDReasoningDrawer } from '@/components/molecules/ICDReasoningDrawer';

export interface ICD10SearchWidgetProps {
  /** Currently selected codes */
  codes: ICDCode[];
  /** Called when codes change */
  onChange: (codes: ICDCode[]) => void;
  /** Whether in read-only mode */
  readOnly?: boolean;
}

/**
 * ICD-10 Code Search and Selection Widget
 */
export const ICD10SearchWidget: React.FC<ICD10SearchWidgetProps> = ({
  codes,
  onChange,
  readOnly = false,
}) => {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const openReasoning = useICDReasoningDrawer();

  const { data: results, isLoading } = useQuery({
    queryKey: ['icd-search', query],
    queryFn: () => searchICD(query, 15),
    enabled: query.length >= 2,
    staleTime: 60_000,
  });

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node) &&
        !inputRef.current?.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const addCode = (result: ICDSearchResult) => {
    if (codes.some((c) => c.code === result.code)) return;
    onChange([
      ...codes,
      {
        code: result.code,
        description: result.description,
        confidence: result.relevance_score,
        ai_suggested: false,
        category: result.category,
      },
    ]);
    setQuery('');
    setIsOpen(false);
  };

  const removeCode = (code: string) => {
    onChange(codes.filter((c) => c.code !== code));
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
          <span className="flex h-5 w-5 items-center justify-center rounded bg-primary-700 text-xs font-bold text-teal-300">ICD</span>
          ICD-10 Diagnosis Codes
        </h4>
        <span className="text-xs text-gray-500">{codes.length} code{codes.length !== 1 ? 's' : ''}</span>
      </div>

      {/* Selected codes */}
      <div className="space-y-2">
        {codes.length === 0 && (
          <p className="text-xs text-gray-500 italic py-2">No ICD-10 codes assigned</p>
        )}
        {codes.map((code) => (
          <div
            key={code.code}
            className="flex items-start justify-between gap-2 rounded-lg bg-primary-800/50 border border-primary-700 p-3 hover:border-teal-700/50 transition-colors"
          >
            <button
              type="button"
              onClick={() =>
                openReasoning({
                  code: code.code,
                  description: code.description,
                  confidence: code.confidence,
                  category: code.category,
                })
              }
              aria-label={`Show AI reasoning for ${code.code}`}
              className="flex items-start gap-2 min-w-0 flex-1 text-left group min-h-[44px]"
            >
              <span className="font-mono text-sm font-semibold text-teal-300 shrink-0 group-hover:text-teal-200">
                {code.code}
              </span>
              <div className="min-w-0">
                <p className="text-sm text-gray-200 leading-snug group-hover:text-white">
                  {code.description}
                </p>
                <div className="flex items-center gap-2 mt-1 flex-wrap">
                  {code.ai_suggested && (
                    <Badge variant="teal" size="sm">AI Suggested</Badge>
                  )}
                  <ConfidencePill value={code.confidence} size="sm" />
                  <span className="text-[10px] text-teal-500/80 group-hover:text-teal-300 uppercase tracking-wider">
                    Why?
                  </span>
                </div>
              </div>
            </button>

            {!readOnly && (
              <button
                onClick={() => removeCode(code.code)}
                aria-label={`Remove ICD code ${code.code}`}
                className="shrink-0 p-1 text-gray-500 hover:text-red-400 rounded transition-colors min-h-[32px] min-w-[32px] flex items-center justify-center"
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
        ))}
      </div>

      {/* Search input */}
      {!readOnly && (
        <div className="relative">
          <div className="relative">
            <svg
              className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              ref={inputRef}
              type="search"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setIsOpen(e.target.value.length >= 2);
              }}
              onFocus={() => query.length >= 2 && setIsOpen(true)}
              placeholder="Search ICD-10 codes (e.g., hypertension, I10)..."
              aria-label="Search ICD-10 codes"
              aria-autocomplete="list"
              aria-expanded={isOpen}
              className={clsx(
                'w-full pl-9 pr-4 py-2.5 text-sm rounded-lg',
                'bg-primary-900 border border-primary-700 text-gray-100 placeholder-gray-500',
                'focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500',
                'min-h-[44px]'
              )}
            />
            {isLoading && (
              <Spinner size="sm" className="absolute right-3 top-1/2 -translate-y-1/2" />
            )}
          </div>

          {/* Search results dropdown */}
          {isOpen && results && results.length > 0 && (
            <div
              ref={dropdownRef}
              role="listbox"
              aria-label="ICD-10 search results"
              className={clsx(
                'absolute z-50 top-full mt-1 w-full',
                'bg-primary-800 border border-primary-600 rounded-lg shadow-xl',
                'max-h-64 overflow-y-auto'
              )}
            >
              {results.map((result) => {
                const isSelected = codes.some((c) => c.code === result.code);
                return (
                  <button
                    key={result.code}
                    role="option"
                    aria-selected={isSelected}
                    onClick={() => addCode(result)}
                    disabled={isSelected}
                    className={clsx(
                      'w-full flex items-start gap-3 px-4 py-3 text-left',
                      'hover:bg-primary-700 transition-colors',
                      'border-b border-primary-700/50 last:border-0',
                      isSelected && 'opacity-50 cursor-not-allowed'
                    )}
                  >
                    <span className="font-mono text-sm font-semibold text-teal-300 shrink-0 mt-0.5">
                      {result.code}
                    </span>
                    <div>
                      <p className="text-sm text-gray-100">{result.description}</p>
                      <p className="text-xs text-gray-500 mt-0.5">{result.category}</p>
                    </div>
                    {isSelected && (
                      <svg className="h-4 w-4 text-green-400 shrink-0 ml-auto mt-0.5" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    )}
                  </button>
                );
              })}
            </div>
          )}

          {isOpen && query.length >= 2 && !isLoading && (!results || results.length === 0) && (
            <div className="absolute z-50 top-full mt-1 w-full bg-primary-800 border border-primary-600 rounded-lg p-4 text-center">
              <p className="text-sm text-gray-400">No ICD-10 codes found for "{query}"</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
