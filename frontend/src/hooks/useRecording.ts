/**
 * Recording hook for ClinNote AI
 *
 * Manages WebRTC MediaRecorder lifecycle, audio chunking,
 * and integration with the WebSocket streaming hook.
 *
 * @example
 * const { startRecording, stopRecording, pauseRecording, status } = useRecording(sessionId);
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRecordingStore } from '@/store/recordingStore';
import type { SessionStatus } from '@/types/recording';
import { useWebSocket } from './useWebSocket';
import {
  requestMicrophoneAccess,
  getSupportedMimeType,
  arrayBufferToBase64,
  calculateAudioLevel,
  stopMediaStream,
  MAX_RECORDING_MINUTES,
  CHUNK_INTERVAL_MS,
} from '@/utils/audioUtils';

export interface UseRecordingReturn {
  /** Start recording for a session */
  startRecording: (sessionId: string) => Promise<void>;
  /** Stop recording and trigger note generation */
  stopRecording: () => void;
  /** Pause the recording */
  pauseRecording: () => void;
  /** Resume a paused recording */
  resumeRecording: () => void;
  /** Current recording status */
  status: SessionStatus | 'idle';
  /** Recording duration in seconds */
  duration: number;
  /** Current audio level 0-1 */
  audioLevel: number;
  /** Whether the WebSocket is connected */
  wsConnected: boolean;
  /** Error message if any */
  error: string | null;
}

const MAX_RECORDING_SECONDS = MAX_RECORDING_MINUTES * 60;

export function useRecording(
  onTranscriptReady?: (sessionId: string, transcriptId: string) => void
): UseRecordingReturn {
  const streamRef = useRef<MediaStream | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const durationTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioLevelTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const chunkIndexRef = useRef(0);
  const offlineBufferRef = useRef<string[]>([]);

  const [localError, setLocalError] = useState<string | null>(null);

  const {
    status,
    duration,
    audioLevel,
    setStatus,
    setAudioLevel,
    setError,
    setDuration,
    setWsConnected,
    incrementDuration,
  } = useRecordingStore();

  const { connect, disconnect, sendAudioChunk, sendStop, isConnected, error: wsError } =
    useWebSocket(onTranscriptReady);

  // Start duration timer
  const startDurationTimer = useCallback(() => {
    durationTimerRef.current = setInterval(() => {
      incrementDuration();
    }, 1000);
  }, [incrementDuration]);

  // Stop duration timer
  const stopDurationTimer = useCallback(() => {
    if (durationTimerRef.current) {
      clearInterval(durationTimerRef.current);
      durationTimerRef.current = null;
    }
  }, []);

  // Start audio level monitoring
  const startAudioLevelMonitor = useCallback((stream: MediaStream) => {
    try {
      audioContextRef.current = new AudioContext();
      analyserRef.current = audioContextRef.current.createAnalyser();
      analyserRef.current.fftSize = 256;

      const source = audioContextRef.current.createMediaStreamSource(stream);
      source.connect(analyserRef.current);

      const buffer = new Float32Array(analyserRef.current.fftSize);

      audioLevelTimerRef.current = setInterval(() => {
        if (analyserRef.current) {
          analyserRef.current.getFloatTimeDomainData(buffer);
          const level = calculateAudioLevel(buffer);
          setAudioLevel(level);
        }
      }, 100);
    } catch {
      // Audio level monitoring is non-critical
    }
  }, [setAudioLevel]);

  // Stop audio level monitoring
  const stopAudioLevelMonitor = useCallback(() => {
    if (audioLevelTimerRef.current) {
      clearInterval(audioLevelTimerRef.current);
      audioLevelTimerRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => undefined);
      audioContextRef.current = null;
    }
    setAudioLevel(0);
  }, [setAudioLevel]);

  /**
   * Start a recording session
   */
  const startRecording = useCallback(
    async (sessionId: string): Promise<void> => {
      try {
        setLocalError(null);
        setError(null);

        // Screenshot mock: skip real audio capture so demo screenshots
        // can show the "recording in progress" UI without a mic device.
        if (
          typeof window !== 'undefined' &&
          (window as unknown as { __CLINNOTE_SCREENSHOT_MODE?: boolean }).__CLINNOTE_SCREENSHOT_MODE
        ) {
          setStatus('recording');
          setDuration(47);
          setAudioLevel(0.6);
          setWsConnected(true);
          return;
        }

        // Request microphone access
        const stream = await requestMicrophoneAccess();
        streamRef.current = stream;

        // Connect WebSocket
        connect(sessionId);

        // Set up MediaRecorder
        const mimeType = getSupportedMimeType();
        const mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
        mediaRecorderRef.current = mediaRecorder;
        chunkIndexRef.current = 0;

        // Handle audio data chunks
        mediaRecorder.ondataavailable = async (event: BlobEvent) => {
          if (event.data.size === 0) return;

          try {
            const arrayBuffer = await event.data.arrayBuffer();
            const base64 = arrayBufferToBase64(arrayBuffer);

            if (isConnected) {
              // Send any buffered chunks first
              while (offlineBufferRef.current.length > 0) {
                const buffered = offlineBufferRef.current.shift()!;
                sendAudioChunk(buffered, chunkIndexRef.current++);
              }
              sendAudioChunk(base64, chunkIndexRef.current++);
            } else {
              // Buffer up to 60 seconds of audio offline
              const maxBufferChunks = Math.floor(60_000 / CHUNK_INTERVAL_MS);
              if (offlineBufferRef.current.length < maxBufferChunks) {
                offlineBufferRef.current.push(base64);
              }
            }
          } catch (err) {
            console.error('Failed to process audio chunk:', err);
          }
        };

        mediaRecorder.onerror = (event) => {
          const errMsg = `Recording error: ${(event as ErrorEvent).message ?? 'unknown'}`;
          setLocalError(errMsg);
          setError(errMsg);
          setStatus('failed');
        };

        // Start recording with chunk interval
        mediaRecorder.start(CHUNK_INTERVAL_MS);

        // Start monitoring
        startAudioLevelMonitor(stream);
        startDurationTimer();
        setStatus('recording');

        // Auto-stop at 120 minutes
        setTimeout(() => {
          if (mediaRecorderRef.current?.state === 'recording') {
            stopRecording();
          }
        }, MAX_RECORDING_SECONDS * 1000);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to start recording';
        setLocalError(message);
        setError(message);
        setStatus('failed');
        throw err;
      }
    },
    [
      connect,
      isConnected,
      sendAudioChunk,
      setStatus,
      setError,
      setDuration,
      setAudioLevel,
      setWsConnected,
      startAudioLevelMonitor,
      startDurationTimer,
    ]
  );

  /**
   * Stop recording and finalize
   */
  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }

    stopDurationTimer();
    stopAudioLevelMonitor();

    if (streamRef.current) {
      stopMediaStream(streamRef.current);
      streamRef.current = null;
    }

    // Tell the server we're done
    sendStop();
    setStatus('processing');
  }, [sendStop, setStatus, stopDurationTimer, stopAudioLevelMonitor]);

  /**
   * Pause recording
   */
  const pauseRecording = useCallback(() => {
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.pause();
      stopDurationTimer();
      setStatus('paused');
    }
  }, [setStatus, stopDurationTimer]);

  /**
   * Resume recording
   */
  const resumeRecording = useCallback(() => {
    if (mediaRecorderRef.current?.state === 'paused') {
      mediaRecorderRef.current.resume();
      startDurationTimer();
      setStatus('recording');
    }
  }, [setStatus, startDurationTimer]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopDurationTimer();
      stopAudioLevelMonitor();
      if (streamRef.current) stopMediaStream(streamRef.current);
      disconnect();
    };
  }, [stopDurationTimer, stopAudioLevelMonitor, disconnect]);

  return {
    startRecording,
    stopRecording,
    pauseRecording,
    resumeRecording,
    status,
    duration,
    audioLevel,
    wsConnected: isConnected,
    error: localError ?? wsError,
  };
}
