/**
 * useTypewriter hook for ClinNote AI
 *
 * Animates incoming text with a fast typewriter effect.
 * Falls back to instant render for very long strings to stay under ~800ms total.
 *
 * @example
 * const displayed = useTypewriter(soapText);
 */

import { useEffect, useRef, useState } from 'react';

const MS_PER_CHAR = 14; // ~70ch/sec
const MAX_TOTAL_MS = 800;

export interface UseTypewriterOptions {
  /** Disable animation entirely (e.g., user prefers reduced motion) */
  disabled?: boolean;
  /** Minimum length before kicking in animation. Short strings just appear. */
  minLength?: number;
}

/**
 * Returns the progressively-typed text. Restarts when `text` changes.
 */
export function useTypewriter(text: string, options: UseTypewriterOptions = {}): string {
  const { disabled = false, minLength = 4 } = options;
  const [displayed, setDisplayed] = useState<string>(text);
  const lastTextRef = useRef<string>(text);

  useEffect(() => {
    // Skip animation if disabled, empty, or text didn't change
    if (disabled || !text || text.length < minLength) {
      setDisplayed(text);
      lastTextRef.current = text;
      return;
    }

    // If user prefers reduced motion, skip
    const prefersReduced =
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReduced) {
      setDisplayed(text);
      lastTextRef.current = text;
      return;
    }

    // If text is very long, the per-char delay would exceed budget — fade in instead.
    const totalMs = Math.min(MAX_TOTAL_MS, text.length * MS_PER_CHAR);
    const effectivePerChar = totalMs / text.length;

    lastTextRef.current = text;
    setDisplayed('');

    let i = 0;
    let raf = 0;
    const start = performance.now();
    const step = (now: number) => {
      if (lastTextRef.current !== text) return; // text changed mid-animation
      const elapsed = now - start;
      const targetCount = Math.min(text.length, Math.floor(elapsed / effectivePerChar));
      if (targetCount > i) {
        i = targetCount;
        setDisplayed(text.slice(0, i));
      }
      if (i < text.length) {
        raf = requestAnimationFrame(step);
      } else {
        setDisplayed(text);
      }
    };
    raf = requestAnimationFrame(step);

    return () => cancelAnimationFrame(raf);
  }, [text, disabled, minLength]);

  return displayed;
}
