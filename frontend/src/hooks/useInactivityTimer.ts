/**
 * HIPAA Inactivity Timer hook for ClinNote AI
 *
 * Tracks user inactivity and enforces session timeout:
 * - At 14 minutes: shows warning modal
 * - At 15 minutes: clears PHI, redirects to /login
 *
 * @example
 * const { showWarning, minutesRemaining, resetTimer } = useInactivityTimer();
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { useNoteStore } from '@/store/noteStore';
import { useRecordingStore } from '@/store/recordingStore';
import { tokenStorage } from '@/api/client';

const INACTIVITY_TIMEOUT_MS = 15 * 60 * 1000; // 15 minutes
const WARNING_AT_MS = 14 * 60 * 1000; // 14 minutes

const ACTIVITY_EVENTS = ['mousedown', 'keydown', 'touchstart', 'scroll'] as const;

export interface UseInactivityTimerReturn {
  /** Whether the warning modal should be shown */
  showWarning: boolean;
  /** Seconds remaining until forced logout */
  secondsRemaining: number;
  /** Manually reset the inactivity timer */
  resetTimer: () => void;
  /** Dismiss the warning and reset the timer */
  dismissWarning: () => void;
}

export function useInactivityTimer(): UseInactivityTimerReturn {
  const navigate = useNavigate();
  const { clearAuth } = useAuthStore();
  const { reset: resetNoteStore } = useNoteStore();
  const { reset: resetRecordingStore } = useRecordingStore();

  const [showWarning, setShowWarning] = useState(false);
  const [secondsRemaining, setSecondsRemaining] = useState(60);

  const lastActivityRef = useRef(Date.now());
  const warningTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const logoutTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const countdownIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearAllTimers = useCallback(() => {
    if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
    if (logoutTimerRef.current) clearTimeout(logoutTimerRef.current);
    if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current);
    warningTimerRef.current = null;
    logoutTimerRef.current = null;
    countdownIntervalRef.current = null;
  }, []);

  const forceLogout = useCallback(() => {
    // Clear all PHI from memory
    clearAllTimers();
    setShowWarning(false);

    // Clear all stores
    clearAuth();
    resetNoteStore();
    resetRecordingStore();
    tokenStorage.clearTokens();

    // Redirect to login
    navigate('/login', { replace: true, state: { reason: 'inactivity' } });
  }, [clearAllTimers, clearAuth, resetNoteStore, resetRecordingStore, navigate]);

  const startCountdown = useCallback(() => {
    setSecondsRemaining(60);
    setShowWarning(true);

    countdownIntervalRef.current = setInterval(() => {
      setSecondsRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(countdownIntervalRef.current!);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  }, []);

  const resetTimer = useCallback(() => {
    lastActivityRef.current = Date.now();
    setShowWarning(false);
    setSecondsRemaining(60);
    clearAllTimers();

    // Set warning timer
    warningTimerRef.current = setTimeout(() => {
      startCountdown();
    }, WARNING_AT_MS);

    // Set logout timer
    logoutTimerRef.current = setTimeout(() => {
      forceLogout();
    }, INACTIVITY_TIMEOUT_MS);
  }, [clearAllTimers, startCountdown, forceLogout]);

  const dismissWarning = useCallback(() => {
    resetTimer();
  }, [resetTimer]);

  // Set up activity event listeners
  useEffect(() => {
    const handleActivity = () => {
      if (Date.now() - lastActivityRef.current > 1000) {
        resetTimer();
      }
    };

    ACTIVITY_EVENTS.forEach((event) => {
      document.addEventListener(event, handleActivity, { passive: true });
    });

    // Start the initial timer
    resetTimer();

    return () => {
      ACTIVITY_EVENTS.forEach((event) => {
        document.removeEventListener(event, handleActivity);
      });
      clearAllTimers();
    };
  }, [resetTimer, clearAllTimers]);

  return { showWarning, secondsRemaining, resetTimer, dismissWarning };
}
