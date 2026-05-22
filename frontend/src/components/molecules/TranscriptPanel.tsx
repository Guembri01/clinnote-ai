/**
 * TranscriptPanel molecule for ClinNote AI
 *
 * Scrollable real-time transcript panel with speaker labels.
 * Auto-scrolls to the bottom as new transcripts arrive.
 *
 * @example
 * <TranscriptPanel transcripts={partialTranscripts} isCollapsed={false} />
 */

import React, { useEffect, useRef, useState } from 'react';
import { clsx } from 'clsx';
import type { PartialTranscript } from '@/types/recording';

export interface TranscriptPanelProps {
  /** Partial transcripts from WebSocket */
  transcripts: PartialTranscript[];
  /** Whether the panel is collapsed */
  isCollapsed?: boolean;
  /** Toggle collapse callback */
  onToggleCollapse?: () => void;
  /** Optional CSS classes */
  className?: string;
}

const speakerColors = {
  physician: 'text-teal-300',
  patient: 'text-blue-300',
  unknown: 'text-gray-400',
};

const speakerLabels = {
  physician: 'Physician',
  patient: 'Patient',
  unknown: 'Speaker',
};

/**
 * Real-time Transcript Panel
 */
export const TranscriptPanel: React.FC<TranscriptPanelProps> = ({
  transcripts,
  isCollapsed = false,
  onToggleCollapse,
  className,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // Auto-scroll to bottom on new transcripts
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [transcripts, autoScroll]);

  // Detect manual scroll up to disable auto-scroll
  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50;
    setAutoScroll(isAtBottom);
  };

  return (
    <div
      className={clsx(
        'flex flex-col rounded-xl border border-primary-700 bg-primary-900/50',
        'transition-all duration-300',
        className
      )}
    >
      {/* Panel header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-primary-700">
        <div className="flex items-center gap-2">
          <svg className="h-4 w-4 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <h3 className="text-sm font-semibold text-gray-200">Live Transcript</h3>
          {transcripts.length > 0 && (
            <span className="text-xs text-gray-500 font-mono">
              {transcripts.length} segments
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {!autoScroll && (
            <button
              onClick={() => {
                setAutoScroll(true);
                scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
              }}
              className="text-xs text-teal-400 hover:text-teal-300 flex items-center gap-1 min-h-[32px] px-2"
              aria-label="Scroll to bottom"
            >
              <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
              Scroll down
            </button>
          )}

          {onToggleCollapse && (
            <button
              onClick={onToggleCollapse}
              aria-label={isCollapsed ? 'Expand transcript' : 'Collapse transcript'}
              aria-expanded={!isCollapsed}
              className={clsx(
                'p-1.5 rounded-md text-gray-400 hover:text-white hover:bg-primary-800',
                'transition-colors min-h-[32px] min-w-[32px] flex items-center justify-center'
              )}
            >
              <svg
                className={clsx('h-4 w-4 transition-transform', isCollapsed && 'rotate-180')}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                aria-hidden="true"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Transcript content */}
      {!isCollapsed && (
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="overflow-y-auto p-4 space-y-3 max-h-64 scroll-smooth"
          aria-live="polite"
          aria-label="Live transcript"
          role="log"
        >
          {transcripts.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <svg className="h-8 w-8 text-gray-600 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>
              <p className="text-gray-500 text-sm">Waiting for speech...</p>
            </div>
          ) : (
            transcripts.map((transcript, idx) => (
              <div key={idx} className="flex gap-2 animate-fade-in">
                <span
                  className={clsx(
                    'text-xs font-semibold shrink-0 mt-0.5',
                    speakerColors[(transcript.speaker ?? 'unknown') as keyof typeof speakerColors]
                  )}
                >
                  {speakerLabels[(transcript.speaker ?? 'unknown') as keyof typeof speakerLabels]}:
                </span>
                <p className="text-sm text-gray-200 leading-relaxed">{transcript.text}</p>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};
