/**
 * RecordingTimer molecule for ClinNote AI
 *
 * Displays MM:SS timer and animated audio level bars.
 *
 * @example
 * <RecordingTimer duration={125} audioLevel={0.6} isRecording={true} />
 */

import React, { useEffect, useRef } from 'react';
import { clsx } from 'clsx';
import { formatDuration } from '@/utils/formatters';

export interface RecordingTimerProps {
  /** Duration in seconds */
  duration: number;
  /** Audio level 0-1 */
  audioLevel: number;
  /** Whether currently recording */
  isRecording: boolean;
  /** Whether paused */
  isPaused?: boolean;
  /** Optional CSS classes */
  className?: string;
}

/** Number of audio level bars */
const BAR_COUNT = 12;

/**
 * Recording Timer with Audio Level Meter
 */
export const RecordingTimer: React.FC<RecordingTimerProps> = ({
  duration,
  audioLevel,
  isRecording,
  isPaused = false,
  className,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animFrameRef = useRef<number>(0);
  const barsRef = useRef<number[]>(new Array(BAR_COUNT).fill(0.1));

  // Animate audio level bars
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const draw = () => {
      const W = canvas.width;
      const H = canvas.height;
      ctx.clearRect(0, 0, W, H);

      const barWidth = Math.floor(W / BAR_COUNT) - 2;
      const gap = 2;

      barsRef.current = barsRef.current.map((bar, i) => {
        if (!isRecording || isPaused) {
          return bar * 0.95;
        }
        // Simulate natural audio variation
        const base = audioLevel;
        const noise = (Math.random() - 0.5) * 0.3;
        const wave = Math.sin(Date.now() / 200 + i * 0.8) * 0.2;
        return Math.max(0.05, Math.min(1, base + noise + wave));
      });

      barsRef.current.forEach((level, i) => {
        const barHeight = Math.max(4, level * H);
        const x = i * (barWidth + gap);
        const y = (H - barHeight) / 2;

        // Color gradient: teal when active, gray when inactive
        const alpha = isRecording && !isPaused ? 0.9 : 0.3;
        ctx.fillStyle = isRecording && !isPaused
          ? `rgba(15, 155, 142, ${alpha})`
          : `rgba(100, 116, 139, ${alpha})`;

        ctx.beginPath();
        ctx.roundRect(x, y, barWidth, barHeight, 2);
        ctx.fill();
      });

      animFrameRef.current = requestAnimationFrame(draw);
    };

    animFrameRef.current = requestAnimationFrame(draw);

    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [audioLevel, isRecording, isPaused]);

  const isWarning = duration >= 100 * 60; // 100 minutes
  const isDanger = duration >= 115 * 60; // 115 minutes

  return (
    <div
      className={clsx(
        'flex flex-col items-center gap-3',
        className
      )}
      aria-live="polite"
      aria-label={`Recording duration: ${formatDuration(duration)}`}
    >
      {/* Timer display */}
      <div
        className={clsx(
          'font-mono text-4xl font-bold tabular-nums tracking-widest',
          isDanger
            ? 'text-red-400 animate-pulse'
            : isWarning
            ? 'text-amber-400'
            : isRecording
            ? 'text-white'
            : 'text-gray-400'
        )}
      >
        {formatDuration(duration)}
      </div>

      {/* Status text */}
      <div className="flex items-center gap-2">
        {isRecording && !isPaused && (
          <span className="h-2 w-2 rounded-full bg-red-500 animate-pulse" aria-hidden="true" />
        )}
        {isPaused && (
          <span className="h-2 w-2 rounded-full bg-amber-400" aria-hidden="true" />
        )}
        <span className={clsx(
          'text-xs font-medium uppercase tracking-widest',
          isPaused ? 'text-amber-400' : isRecording ? 'text-red-400' : 'text-gray-500'
        )}>
          {isPaused ? 'Paused' : isRecording ? 'Recording' : 'Stopped'}
        </span>
      </div>

      {/* CSS animated waveform bars (always visible when recording/paused) */}
      <div
        className="flex items-center justify-center gap-[3px] h-12"
        aria-hidden="true"
        aria-label="Audio waveform visualizer"
      >
        {Array.from({ length: 12 }).map((_, i) => (
          <span
            key={i}
            className={`waveform-bar${(!isRecording || isPaused) ? ' paused' : ''}`}
            style={{
              height: isRecording && !isPaused ? undefined : '6px',
              opacity: isRecording ? 1 : 0.3,
            }}
          />
        ))}
      </div>

      {/* Canvas audio level meter (hidden, used for precise level sync) */}
      <canvas
        ref={canvasRef}
        width={BAR_COUNT * 10}
        height={40}
        className="sr-only"
        aria-hidden="true"
      />

      {/* Warning for near-max duration */}
      {isWarning && (
        <p className={clsx('text-xs font-medium', isDanger ? 'text-red-400' : 'text-amber-400')}>
          {isDanger ? 'Max duration in 5 min' : 'Approaching 2h limit'}
        </p>
      )}
    </div>
  );
};
