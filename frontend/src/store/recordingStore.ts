/**
 * Recording session Zustand store for ClinNote AI
 */

import { create } from 'zustand';
import type { RecordingSession, SessionStatus, PartialTranscript } from '@/types/recording';

interface RecordingState {
  /** Current recording session */
  session: RecordingSession | null;
  /** Current recording status */
  status: SessionStatus | 'idle';
  /** Recording duration in seconds */
  duration: number;
  /** Accumulated partial transcripts from WebSocket */
  partialTranscripts: PartialTranscript[];
  /** Whether the WebSocket is connected */
  wsConnected: boolean;
  /** Current audio level (0-1) for the meter */
  audioLevel: number;
  /** Error message if recording failed */
  error: string | null;
}

interface RecordingActions {
  setSession: (session: RecordingSession) => void;
  setStatus: (status: RecordingState['status']) => void;
  setDuration: (duration: number) => void;
  incrementDuration: () => void;
  addPartialTranscript: (transcript: PartialTranscript) => void;
  clearPartialTranscripts: () => void;
  setWsConnected: (connected: boolean) => void;
  setAudioLevel: (level: number) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export type RecordingStore = RecordingState & RecordingActions;

const initialState: RecordingState = {
  session: null,
  status: 'idle',
  duration: 0,
  partialTranscripts: [],
  wsConnected: false,
  audioLevel: 0,
  error: null,
};

export const useRecordingStore = create<RecordingStore>()((set) => ({
  ...initialState,

  setSession: (session) => set({ session }),

  setStatus: (status) => set({ status }),

  setDuration: (duration) => set({ duration }),

  incrementDuration: () => set((state) => ({ duration: state.duration + 1 })),

  addPartialTranscript: (transcript) =>
    set((state) => ({
      partialTranscripts: [...state.partialTranscripts.slice(-200), transcript],
    })),

  clearPartialTranscripts: () => set({ partialTranscripts: [] }),

  setWsConnected: (wsConnected) => set({ wsConnected }),

  setAudioLevel: (audioLevel) => set({ audioLevel }),

  setError: (error) => set({ error }),

  reset: () => set(initialState),
}));
