/**
 * SOAP Note editor Zustand store for ClinNote AI
 */

import { create } from 'zustand';
import type { SOAPNote, SOAPSectionType, ICDCode, CPTCode } from '@/types/soap';

interface NoteState {
  /** The current SOAP note being reviewed/edited */
  currentNote: SOAPNote | null;
  /** Edited text per section (only sections with changes) */
  editedSections: Partial<Record<SOAPSectionType, string>>;
  /** Edited ICD codes */
  editedICDCodes: ICDCode[] | null;
  /** Edited CPT codes */
  editedCPTCodes: CPTCode[] | null;
  /** Whether there are unsaved changes */
  hasUnsavedChanges: boolean;
  /** Timestamp of last auto-save */
  lastSavedAt: Date | null;
  /** Whether auto-save is currently in progress */
  isSaving: boolean;
}

interface NoteActions {
  setCurrentNote: (note: SOAPNote) => void;
  updateSection: (section: SOAPSectionType, text: string) => void;
  updateICDCodes: (codes: ICDCode[]) => void;
  updateCPTCodes: (codes: CPTCode[]) => void;
  markSaved: () => void;
  setIsSaving: (saving: boolean) => void;
  clearEdits: () => void;
  reset: () => void;
}

export type NoteStore = NoteState & NoteActions;

const initialState: NoteState = {
  currentNote: null,
  editedSections: {},
  editedICDCodes: null,
  editedCPTCodes: null,
  hasUnsavedChanges: false,
  lastSavedAt: null,
  isSaving: false,
};

export const useNoteStore = create<NoteStore>()((set) => ({
  ...initialState,

  setCurrentNote: (note) =>
    set({
      currentNote: note,
      editedSections: {},
      editedICDCodes: null,
      editedCPTCodes: null,
      hasUnsavedChanges: false,
    }),

  updateSection: (section, text) =>
    set((state) => ({
      editedSections: { ...state.editedSections, [section]: text },
      hasUnsavedChanges: true,
    })),

  updateICDCodes: (codes) =>
    set({ editedICDCodes: codes, hasUnsavedChanges: true }),

  updateCPTCodes: (codes) =>
    set({ editedCPTCodes: codes, hasUnsavedChanges: true }),

  markSaved: () =>
    set({ hasUnsavedChanges: false, lastSavedAt: new Date(), isSaving: false }),

  setIsSaving: (isSaving) => set({ isSaving }),

  clearEdits: () =>
    set({
      editedSections: {},
      editedICDCodes: null,
      editedCPTCodes: null,
      hasUnsavedChanges: false,
    }),

  reset: () => set(initialState),
}));
