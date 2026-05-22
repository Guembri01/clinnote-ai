/**
 * WebSocket hook for real-time audio streaming and transcript reception
 *
 * @example
 * const { connect, disconnect, sendAudioChunk, isConnected } = useWebSocket(sessionId);
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRecordingStore } from '@/store/recordingStore';
import type { WSInboundMessage } from '@/types/recording';
import { tokenStorage } from '@/api/client';

const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL ?? 'ws://localhost:8003';
const MAX_RECONNECT_ATTEMPTS = 5;
const BASE_RECONNECT_DELAY_MS = 1000;

export interface UseWebSocketReturn {
  /** Whether the WebSocket is currently connected */
  isConnected: boolean;
  /** Connect to the WebSocket for a session */
  connect: (sessionId: string) => void;
  /** Disconnect from the WebSocket */
  disconnect: () => void;
  /**
   * Send a base64-encoded audio chunk
   * @param base64Audio - Base64-encoded WAV audio data
   * @param chunkIndex - Sequential chunk number
   */
  sendAudioChunk: (base64Audio: string, chunkIndex: number) => void;
  /** Send stop recording signal */
  sendStop: () => void;
  /** Connection error if any */
  error: string | null;
}

export function useWebSocket(
  onTranscriptReady?: (sessionId: string, transcriptId: string) => void
): UseWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isIntentionalDisconnect = useRef(false);

  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { addPartialTranscript, setWsConnected, setStatus } = useRecordingStore();

  const connect = useCallback((sessionId: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.close();
    }

    sessionIdRef.current = sessionId;
    isIntentionalDisconnect.current = false;
    reconnectAttemptsRef.current = 0;

    const token = tokenStorage.getAccessToken();
    const url = `${WS_BASE_URL}/ws/recording/${sessionId}${token ? `?token=${token}` : ''}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      setWsConnected(true);
      setError(null);
      reconnectAttemptsRef.current = 0;
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const message = JSON.parse(event.data as string) as WSInboundMessage;
        handleMessage(message);
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    ws.onerror = () => {
      setError('WebSocket connection error');
    };

    ws.onclose = (event) => {
      setIsConnected(false);
      setWsConnected(false);

      if (!isIntentionalDisconnect.current && reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        const delay = BASE_RECONNECT_DELAY_MS * Math.pow(2, reconnectAttemptsRef.current);
        reconnectAttemptsRef.current++;

        reconnectTimeoutRef.current = setTimeout(() => {
          if (sessionIdRef.current && !isIntentionalDisconnect.current) {
            connect(sessionIdRef.current);
          }
        }, delay);
      } else if (!isIntentionalDisconnect.current) {
        setError(`Connection lost (code: ${event.code}). Please check your network.`);
      }
    };
  }, [setWsConnected]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleMessage = useCallback(
    (message: WSInboundMessage) => {
      switch (message.type) {
        case 'partial_transcript':
          addPartialTranscript({
            text: message.text,
            speaker: message.speaker as 'physician' | 'patient' | 'unknown' | undefined,
            timestamp: Date.now(),
            is_final: false,
          });
          break;

        case 'processing':
          setStatus('processing');
          break;

        case 'transcript_ready':
          setStatus('completed');
          onTranscriptReady?.(message.session_id, message.transcript_id);
          break;

        case 'error':
          setError(message.message);
          break;

        case 'connected':
          // Successfully connected
          break;
      }
    },
    [addPartialTranscript, setStatus, onTranscriptReady]
  );

  const sendAudioChunk = useCallback(
    (base64Audio: string, chunkIndex: number) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
      if (!sessionIdRef.current) return;

      const message = {
        type: 'audio_chunk',
        data: base64Audio,
        chunk_index: chunkIndex,
        session_id: sessionIdRef.current,
      };

      wsRef.current.send(JSON.stringify(message));
    },
    []
  );

  const sendStop = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    if (!sessionIdRef.current) return;

    wsRef.current.send(
      JSON.stringify({ type: 'stop_recording', session_id: sessionIdRef.current })
    );
  }, []);

  const disconnect = useCallback(() => {
    isIntentionalDisconnect.current = true;

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close(1000, 'User disconnected');
      wsRef.current = null;
    }

    setIsConnected(false);
    setWsConnected(false);
    sessionIdRef.current = null;
  }, [setWsConnected]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      isIntentionalDisconnect.current = true;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  return { isConnected, connect, disconnect, sendAudioChunk, sendStop, error };
}
