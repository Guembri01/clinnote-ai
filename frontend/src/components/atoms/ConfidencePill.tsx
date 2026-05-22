/**
 * ConfidencePill atom for ClinNote AI
 *
 * Animated horizontal confidence indicator with a fill bar.
 * Fills from 0 to `value` over 600ms with a cubic-bezier easing.
 * Color gradient: green ≥90%, amber 70–89%, red <70%.
 *
 * Accepts either a 0–1 score or a 0–100 percent.
 *
 * @example
 * <ConfidencePill value={96} />
 * <ConfidencePill value={0.94} />
 */

import React, { useEffect, useState } from 'react';
import { clsx } from 'clsx';

export interface ConfidencePillProps {
  /** Either 0..1 or 0..100 — auto-detected */
  value: number;
  /** Optional label override (defaults to "confidence") */
  label?: string;
  /** Compact mode — smaller text + bar */
  size?: 'sm' | 'md';
  /** Show the numeric percent? Default true */
  showValue?: boolean;
  className?: string;
}

function normalizePct(value: number): number {
  if (value <= 1) return Math.max(0, Math.min(100, Math.round(value * 100)));
  return Math.max(0, Math.min(100, Math.round(value)));
}

function tierFor(pct: number): { fillCls: string; textCls: string; ringCls: string } {
  if (pct >= 90) {
    return {
      fillCls: 'bg-green-500',
      textCls: 'text-green-300',
      ringCls: 'border-green-700/50 bg-green-900/20',
    };
  }
  if (pct >= 70) {
    return {
      fillCls: 'bg-amber-500',
      textCls: 'text-amber-300',
      ringCls: 'border-amber-700/50 bg-amber-900/20',
    };
  }
  return {
    fillCls: 'bg-red-500',
    textCls: 'text-red-300',
    ringCls: 'border-red-700/50 bg-red-900/20',
  };
}

export const ConfidencePill: React.FC<ConfidencePillProps> = ({
  value,
  label = 'confidence',
  size = 'sm',
  showValue = true,
  className,
}) => {
  const pct = normalizePct(value);
  const [width, setWidth] = useState(0);
  const { fillCls, textCls, ringCls } = tierFor(pct);

  // Animate from 0 to pct on mount / when value changes
  useEffect(() => {
    // Reset to 0 first to retrigger
    setWidth(0);
    const id = requestAnimationFrame(() => {
      // give the browser a frame before applying the transition
      requestAnimationFrame(() => setWidth(pct));
    });
    return () => cancelAnimationFrame(id);
  }, [pct]);

  const heightCls = size === 'md' ? 'h-2' : 'h-1.5';
  const padCls = size === 'md' ? 'px-2.5 py-1.5' : 'px-2 py-1';
  const textSizeCls = size === 'md' ? 'text-xs' : 'text-[10px]';

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-2 rounded-full border',
        padCls,
        ringCls,
        className
      )}
      aria-label={`${pct}% ${label}`}
      role="img"
    >
      <span
        className={clsx('inline-block rounded-full bg-gray-700/60 overflow-hidden', heightCls)}
        style={{ width: size === 'md' ? 72 : 56 }}
        aria-hidden="true"
      >
        <span
          className={clsx('block h-full rounded-full', fillCls)}
          style={{
            width: `${width}%`,
            transition: 'width 600ms cubic-bezier(.4,0,.2,1)',
          }}
        />
      </span>
      {showValue && (
        <span className={clsx('font-semibold tabular-nums', textSizeCls, textCls)}>
          {pct}%
        </span>
      )}
    </span>
  );
};
