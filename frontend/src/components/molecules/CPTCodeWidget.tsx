/**
 * CPTCodeWidget molecule for ClinNote AI
 *
 * CPT code display and inline editing.
 *
 * @example
 * <CPTCodeWidget codes={note.cpt_codes} onChange={updateCPTCodes} />
 */

import React, { useState } from 'react';
import { clsx } from 'clsx';
import type { CPTCode } from '@/types/soap';
import { Badge } from '@/components/atoms/Badge';
import { Button } from '@/components/atoms/Button';

export interface CPTCodeWidgetProps {
  codes: CPTCode[];
  onChange: (codes: CPTCode[]) => void;
  readOnly?: boolean;
}

/**
 * CPT Procedure Code Widget
 */
export const CPTCodeWidget: React.FC<CPTCodeWidgetProps> = ({
  codes,
  onChange,
  readOnly = false,
}) => {
  const [newCode, setNewCode] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [isAdding, setIsAdding] = useState(false);

  const addCode = () => {
    if (!newCode.trim()) return;
    onChange([
      ...codes,
      {
        code: newCode.trim(),
        description: newDesc.trim() || 'Manual entry',
        units: 1,
        ai_suggested: false,
      },
    ]);
    setNewCode('');
    setNewDesc('');
    setIsAdding(false);
  };

  const removeCode = (code: string) => {
    onChange(codes.filter((c) => c.code !== code));
  };

  const updateUnits = (code: string, units: number) => {
    onChange(codes.map((c) => (c.code === code ? { ...c, units } : c)));
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
          <span className="flex h-5 w-5 items-center justify-center rounded bg-primary-700 text-xs font-bold text-primary-300">CPT</span>
          CPT Procedure Codes
        </h4>
        <span className="text-xs text-gray-500">{codes.length} code{codes.length !== 1 ? 's' : ''}</span>
      </div>

      {/* Existing codes */}
      <div className="space-y-2">
        {codes.length === 0 && (
          <p className="text-xs text-gray-500 italic py-2">No CPT codes assigned</p>
        )}
        {codes.map((code) => (
          <div
            key={code.code}
            className="flex items-center gap-3 rounded-lg bg-primary-800/50 border border-primary-700 px-3 py-2.5"
          >
            <span className="font-mono text-sm font-semibold text-primary-300 shrink-0 w-16">
              {code.code}
            </span>
            <p className="text-sm text-gray-200 flex-1 min-w-0 truncate">
              {code.description}
            </p>
            {code.ai_suggested && (
              <Badge variant="teal" size="sm">AI</Badge>
            )}

            {/* Units selector */}
            {!readOnly ? (
              <div className="flex items-center gap-1.5 shrink-0">
                <label htmlFor={`units-${code.code}`} className="text-xs text-gray-400 font-medium">Units</label>
                <input
                  id={`units-${code.code}`}
                  type="number"
                  min="1"
                  max="99"
                  value={code.units ?? 1}
                  onChange={(e) => updateUnits(code.code, parseInt(e.target.value) || 1)}
                  aria-label={`Units for CPT ${code.code}`}
                  className={clsx(
                    'w-14 text-center text-sm bg-primary-900 border border-primary-600 rounded text-gray-100',
                    'py-1 focus:outline-none focus:border-teal-500 min-h-[32px]'
                  )}
                />
              </div>
            ) : (
              <span className="text-xs text-gray-500 shrink-0">×{code.units ?? 1}</span>
            )}

            {!readOnly && (
              <button
                onClick={() => removeCode(code.code)}
                aria-label={`Remove CPT code ${code.code}`}
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

      {/* Add new code form */}
      {!readOnly && (
        <div>
          {!isAdding ? (
            <button
              onClick={() => setIsAdding(true)}
              className={clsx(
                'flex items-center gap-2 text-sm text-teal-400 hover:text-teal-300',
                'transition-colors min-h-[44px] px-2 rounded-lg hover:bg-primary-800'
              )}
              aria-label="Add CPT code"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Add CPT code
            </button>
          ) : (
            <div className="flex gap-2 items-end">
              <input
                type="text"
                value={newCode}
                onChange={(e) => setNewCode(e.target.value)}
                placeholder="Code (e.g. 99213)"
                aria-label="New CPT code"
                className={clsx(
                  'w-28 px-3 py-2 text-sm rounded-lg',
                  'bg-primary-900 border border-primary-700 text-gray-100 placeholder-gray-500',
                  'focus:outline-none focus:border-teal-500 min-h-[44px]'
                )}
              />
              <input
                type="text"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                placeholder="Description"
                aria-label="CPT code description"
                className={clsx(
                  'flex-1 px-3 py-2 text-sm rounded-lg',
                  'bg-primary-900 border border-primary-700 text-gray-100 placeholder-gray-500',
                  'focus:outline-none focus:border-teal-500 min-h-[44px]'
                )}
              />
              <Button size="sm" onClick={addCode} disabled={!newCode.trim()}>
                Add
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setIsAdding(false)}>
                Cancel
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
