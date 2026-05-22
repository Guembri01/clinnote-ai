/**
 * WebRTC audio utilities for ClinNote AI
 *
 * Handles microphone access, AudioContext configuration,
 * and audio chunk extraction for 16kHz mono WAV streaming.
 */

/** Optimal audio constraints for clinical transcription */
export const AUDIO_CONSTRAINTS: MediaStreamConstraints = {
  audio: {
    sampleRate: 16000,
    channelCount: 1,
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
  },
  video: false,
};

/** Target sample rate for Whisper / clinical ASR */
export const TARGET_SAMPLE_RATE = 16000;

/** Audio chunk interval in milliseconds */
export const CHUNK_INTERVAL_MS = 3000;

/** Maximum recording duration in minutes */
export const MAX_RECORDING_MINUTES = 120;

/**
 * Request microphone access with clinical audio settings
 * @throws Error if permission denied or device not available
 */
export async function requestMicrophoneAccess(): Promise<MediaStream> {
  try {
    return await navigator.mediaDevices.getUserMedia(AUDIO_CONSTRAINTS);
  } catch (error) {
    if (error instanceof DOMException) {
      switch (error.name) {
        case 'NotAllowedError':
          throw new Error(
            'Microphone access denied. Please allow microphone access in your browser settings.'
          );
        case 'NotFoundError':
          throw new Error(
            'No microphone found. Please connect a microphone and try again.'
          );
        case 'NotReadableError':
          throw new Error(
            'Microphone is in use by another application. Please close other apps and try again.'
          );
        default:
          throw new Error(`Microphone error: ${error.message}`);
      }
    }
    throw error;
  }
}

/**
 * Convert a Float32Array audio buffer to 16-bit PCM WAV
 * @param float32Array - Audio samples from Web Audio API
 * @param sampleRate - Sample rate of the audio
 * @returns WAV-formatted ArrayBuffer
 */
export function float32ToWav(float32Array: Float32Array, sampleRate: number): ArrayBuffer {
  const numChannels = 1;
  const bitsPerSample = 16;
  const byteRate = (sampleRate * numChannels * bitsPerSample) / 8;
  const blockAlign = (numChannels * bitsPerSample) / 8;
  const dataSize = float32Array.length * 2; // 16-bit = 2 bytes per sample
  const bufferSize = 44 + dataSize;

  const buffer = new ArrayBuffer(bufferSize);
  const view = new DataView(buffer);

  // RIFF header
  writeString(view, 0, 'RIFF');
  view.setUint32(4, bufferSize - 8, true);
  writeString(view, 8, 'WAVE');

  // fmt chunk
  writeString(view, 12, 'fmt ');
  view.setUint32(16, 16, true); // chunk size
  view.setUint16(20, 1, true);  // PCM format
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, byteRate, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, bitsPerSample, true);

  // data chunk
  writeString(view, 36, 'data');
  view.setUint32(40, dataSize, true);

  // Convert float32 samples to int16
  const offset = 44;
  for (let i = 0; i < float32Array.length; i++) {
    const sample = Math.max(-1, Math.min(1, float32Array[i]));
    view.setInt16(offset + i * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
  }

  return buffer;
}

function writeString(view: DataView, offset: number, str: string): void {
  for (let i = 0; i < str.length; i++) {
    view.setUint8(offset + i, str.charCodeAt(i));
  }
}

/**
 * Encode an ArrayBuffer to base64 string
 */
export function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

/**
 * Get the supported MIME type for MediaRecorder
 */
export function getSupportedMimeType(): string {
  const types = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4',
  ];
  for (const type of types) {
    if (MediaRecorder.isTypeSupported(type)) return type;
  }
  return '';
}

/**
 * Calculate audio level (RMS) from a Float32Array
 * @returns Value between 0 and 1
 */
export function calculateAudioLevel(buffer: Float32Array): number {
  let sum = 0;
  for (let i = 0; i < buffer.length; i++) {
    sum += buffer[i] * buffer[i];
  }
  const rms = Math.sqrt(sum / buffer.length);
  return Math.min(1, rms * 5); // Scale up for visibility
}

/**
 * Stop all tracks in a media stream
 */
export function stopMediaStream(stream: MediaStream): void {
  stream.getTracks().forEach((track) => track.stop());
}
