/**
 * SOAP Note editor hook for ClinNote AI
 *
 * Manages note editing state, auto-save (every 30s), and diff tracking.
 *
 * @example
 * const { editSection, saveNote, hasUnsavedChanges, lastSavedAt } = useNoteEditor(noteId);
 */

import { useCallback, useEffect, useRef } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNoteStore } from '@/store/noteStore';
import { editNote } from '@/api/notes';
import type { SOAPSectionType, ICDCode, CPTCode } from '@/types/soap';

const AUTO_SAVE_INTERVAL_MS = 30_000; // 30 seconds

export interface UseNoteEditorReturn {
  /** Edit a specific SOAP section */
  editSection: (section: SOAPSectionType, text: string) => void;
  /** Update ICD codes */
  updateICDCodes: (codes: ICDCode[]) => void;
  /** Update CPT codes */
  updateCPTCodes: (codes: CPTCode[]) => void;
  /** Manually save the note */
  saveNote: () => Promise<void>;
  /** Whether there are unsaved changes */
  hasUnsavedChanges: boolean;
  /** Last auto-save timestamp */
  lastSavedAt: Date | null;
  /** Whether save is in progress */
  isSaving: boolean;
  /** Save error if any */
  saveError: string | null;
}

export function useNoteEditor(noteId: string | undefined): UseNoteEditorReturn {
  const queryClient = useQueryClient();
  const autoSaveTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const {
    editedSections,
    editedICDCodes,
    editedCPTCodes,
    hasUnsavedChanges,
    lastSavedAt,
    isSaving,
    updateSection,
    updateICDCodes,
    updateCPTCodes,
    setIsSaving,
    markSaved,
  } = useNoteStore();

  const { mutateAsync: mutateNote, error: mutateError } = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Parameters<typeof editNote>[1] }) =>
      editNote(id, payload),
    onSuccess: (updatedNote) => {
      queryClient.setQueryData(['note', noteId], updatedNote);
      markSaved();
    },
  });

  const saveNote = useCallback(async (): Promise<void> => {
    if (!noteId || !hasUnsavedChanges) return;

    setIsSaving(true);

    try {
      // Save each modified section
      for (const [section, text] of Object.entries(editedSections) as [SOAPSectionType, string][]) {
        await mutateNote({ id: noteId, payload: { section, text } });
      }

      // Save code changes
      if (editedICDCodes !== null) {
        await mutateNote({ id: noteId, payload: { icd_codes: editedICDCodes } });
      }
      if (editedCPTCodes !== null) {
        await mutateNote({ id: noteId, payload: { cpt_codes: editedCPTCodes } });
      }

      markSaved();
    } catch {
      setIsSaving(false);
    }
  }, [noteId, hasUnsavedChanges, editedSections, editedICDCodes, editedCPTCodes, mutateNote, setIsSaving, markSaved]);

  // Auto-save every 30 seconds if there are unsaved changes
  useEffect(() => {
    if (autoSaveTimerRef.current) clearInterval(autoSaveTimerRef.current);

    autoSaveTimerRef.current = setInterval(() => {
      if (hasUnsavedChanges && noteId) {
        saveNote();
      }
    }, AUTO_SAVE_INTERVAL_MS);

    return () => {
      if (autoSaveTimerRef.current) clearInterval(autoSaveTimerRef.current);
    };
  }, [hasUnsavedChanges, noteId, saveNote]);

  // Keyboard shortcut: Ctrl+S to save
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        saveNote();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [saveNote]);

  return {
    editSection: updateSection,
    updateICDCodes,
    updateCPTCodes,
    saveNote,
    hasUnsavedChanges,
    lastSavedAt,
    isSaving,
    saveError: mutateError ? (mutateError as Error).message : null,
  };
}
