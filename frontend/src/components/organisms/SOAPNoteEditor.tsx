/**
 * SOAPNoteEditor organism for ClinNote AI
 *
 * Full SOAP editor with all 4 sections, ICD-10 codes, CPT codes,
 * auto-save indicator, diff view, and keyboard shortcuts.
 *
 * @example
 * <SOAPNoteEditor note={soapNote} />
 */

import React, { useState } from 'react';
import { clsx } from 'clsx';
import { useNoteEditor } from '@/hooks/useNoteEditor';
import { useNoteStore } from '@/store/noteStore';
import { SOAPSection } from '@/components/molecules/SOAPSection';
import { ICD10SearchWidget } from '@/components/molecules/ICD10SearchWidget';
import { CPTCodeWidget } from '@/components/molecules/CPTCodeWidget';
import { NoteStatusBar } from '@/components/molecules/NoteStatusBar';
import { Button } from '@/components/atoms/Button';
import { Spinner } from '@/components/atoms/Spinner';
import type { SOAPNote, SOAPSectionType } from '@/types/soap';
import { formatRelativeTime } from '@/utils/formatters';

export interface SOAPNoteEditorProps {
  note: SOAPNote;
  readOnly?: boolean;
}

const SOAP_SECTIONS: SOAPSectionType[] = ['subjective', 'objective', 'assessment', 'plan'];

/**
 * Full SOAP Note Editor
 */
export const SOAPNoteEditor: React.FC<SOAPNoteEditorProps> = ({
  note,
  readOnly = false,
}) => {
  const [showDiff, setShowDiff] = useState(false);
  const { editedSections, editedICDCodes, editedCPTCodes } = useNoteStore();

  const {
    editSection,
    updateICDCodes,
    updateCPTCodes,
    saveNote,
    hasUnsavedChanges,
    lastSavedAt,
    isSaving,
    saveError,
  } = useNoteEditor(note.id);

  const currentICDCodes = editedICDCodes ?? note.icd_codes;
  const currentCPTCodes = editedCPTCodes ?? note.cpt_codes;

  return (
    <div className="flex flex-col gap-4">
      {/* Status bar */}
      <NoteStatusBar note={note} />

      {/* Editor toolbar */}
      {!readOnly && (
        <div className="flex items-center justify-between px-1">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowDiff(!showDiff)}
              aria-pressed={showDiff}
              className={clsx(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium',
                'transition-colors min-h-[36px]',
                showDiff
                  ? 'bg-primary-700 text-teal-300 border border-primary-600'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-primary-800 border border-transparent'
              )}
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              {showDiff ? 'Hide AI vs. Edited Diff' : 'Show AI vs. Edited Diff'}
            </button>
          </div>

          {/* Save status */}
          <div className="flex items-center gap-3">
            {saveError && (
              <p className="text-xs text-red-400">Save failed</p>
            )}
            {isSaving ? (
              <div className="flex items-center gap-1.5 text-xs text-gray-400">
                <Spinner size="xs" />
                <span>Saving...</span>
              </div>
            ) : lastSavedAt ? (
              <p className="text-xs text-gray-500">
                Saved {formatRelativeTime(lastSavedAt.toISOString())}
              </p>
            ) : null}

            {hasUnsavedChanges && !isSaving && (
              <Button
                variant="secondary"
                size="sm"
                onClick={saveNote}
                aria-label="Save note (Ctrl+S)"
                leftIcon={
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                  </svg>
                }
              >
                Save (Ctrl+S)
              </Button>
            )}
          </div>
        </div>
      )}

      {/* SOAP sections */}
      <div className="space-y-3">
        {SOAP_SECTIONS.map((sectionType) => {
          const section = {
            ...note.sections[sectionType],
            physician_edited_text:
              editedSections[sectionType] !== undefined
                ? editedSections[sectionType]!
                : note.sections[sectionType].physician_edited_text,
            is_modified:
              editedSections[sectionType] !== undefined ||
              note.sections[sectionType].is_modified,
          };

          return (
            <SOAPSection
              key={sectionType}
              type={sectionType}
              section={section}
              onChange={(text) => editSection(sectionType, text)}
              readOnly={readOnly}
              showDiff={showDiff}
            />
          );
        })}
      </div>

      {/* Codes section */}
      <div className="rounded-xl border border-primary-700 bg-primary-900/30 p-4 space-y-6">
        <ICD10SearchWidget
          codes={currentICDCodes}
          onChange={updateICDCodes}
          readOnly={readOnly}
        />

        <div className="border-t border-primary-700 pt-6">
          <CPTCodeWidget
            codes={currentCPTCodes}
            onChange={updateCPTCodes}
            readOnly={readOnly}
          />
        </div>
      </div>

      {/* AI attribution */}
      <div className="flex items-center gap-2 px-1">
        <svg className="h-3.5 w-3.5 text-teal-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
        <p className="text-xs text-gray-500">
          AI-generated content. Always verify clinical accuracy before approving.
        </p>
      </div>
    </div>
  );
};
