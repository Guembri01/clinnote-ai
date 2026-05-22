/**
 * ICDReasoningDrawer molecule for ClinNote AI
 *
 * Right-side slide-in panel that explains why the AI selected a given
 * ICD-10 code. Bullet citations are mocked but realistic — sourced
 * from each SOAP section so reviewers can audit the chain of reasoning.
 *
 * Usage:
 *   import { useICDReasoningDrawer, ICDReasoningDrawerHost } from './ICDReasoningDrawer';
 *
 *   // Once, near the AppShell root:
 *   <ICDReasoningDrawerHost />
 *
 *   // Anywhere in the tree:
 *   const open = useICDReasoningDrawer();
 *   <button onClick={() => open({ code: 'E11.65', description: 'Type 2 DM w/ hyperglycemia', confidence: 0.94 })}>
 *     Why?
 *   </button>
 */

import React, { useEffect, useState } from 'react';
import { create } from 'zustand';
import { clsx } from 'clsx';
import { ConfidencePill } from '@/components/atoms/ConfidencePill';
import { useEscapeKey } from '@/hooks/useEscapeKey';

export interface ReasoningCitation {
  /** The SOAP section the citation came from */
  source: 'Subjective' | 'Objective' | 'Assessment' | 'Plan' | 'Transcript';
  /** A short quoted excerpt */
  excerpt: string;
  /** Why this excerpt supports the code */
  rationale: string;
}

export interface ICDReasoningPayload {
  code: string;
  description: string;
  /** 0..1 or 0..100 */
  confidence: number;
  /** Optional category, e.g., "Endocrine, nutritional and metabolic diseases" */
  category?: string;
  /** Optional citations — if omitted, realistic mocks are generated. */
  citations?: ReasoningCitation[];
}

interface DrawerStore {
  isOpen: boolean;
  payload: ICDReasoningPayload | null;
  open: (payload: ICDReasoningPayload) => void;
  close: () => void;
}

const useDrawerStore = create<DrawerStore>((set) => ({
  isOpen: false,
  payload: null,
  open: (payload) => set({ isOpen: true, payload }),
  close: () => set({ isOpen: false }),
}));

/**
 * Public hook — returns a function to open the drawer with any payload.
 */
export function useICDReasoningDrawer(): (payload: ICDReasoningPayload) => void {
  return useDrawerStore((s) => s.open);
}

/** Fallback realistic citations by code prefix */
function mockCitations(code: string): ReasoningCitation[] {
  const prefix = code.split('.')[0]?.toUpperCase() ?? '';

  if (prefix.startsWith('E11')) {
    return [
      {
        source: 'Subjective',
        excerpt: 'patient reports persistent fatigue and increased thirst over 4 weeks',
        rationale: 'Classic polydipsia + fatigue pattern consistent with uncontrolled Type 2 DM.',
      },
      {
        source: 'Objective',
        excerpt: 'fasting glucose 218 mg/dL; HbA1c 9.4%',
        rationale: 'HbA1c above 9% confirms hyperglycemia — supports E11.65 (with hyperglycemia).',
      },
      {
        source: 'Assessment',
        excerpt: 'patient currently on metformin 1000mg BID; not at goal',
        rationale: 'Existing T2DM diagnosis with documented poor glycemic control.',
      },
    ];
  }
  if (prefix.startsWith('I10') || prefix === 'I10') {
    return [
      {
        source: 'Objective',
        excerpt: 'BP 154/96 mmHg (avg of 3 readings); HR 84',
        rationale: 'Stage 2 hypertension on today\'s vitals.',
      },
      {
        source: 'Subjective',
        excerpt: 'patient reports occasional morning headaches',
        rationale: 'Symptom commonly associated with elevated systolic BP.',
      },
      {
        source: 'Plan',
        excerpt: 'initiate lisinopril 10mg daily; recheck in 2 weeks',
        rationale: 'Treatment plan implies primary hypertension as working diagnosis.',
      },
    ];
  }
  if (prefix.startsWith('J45')) {
    return [
      {
        source: 'Subjective',
        excerpt: 'patient reports wheezing and shortness of breath with exertion',
        rationale: 'Hallmark asthma symptoms.',
      },
      {
        source: 'Objective',
        excerpt: 'auscultation reveals bilateral end-expiratory wheezes',
        rationale: 'Physical exam consistent with reactive airway disease.',
      },
      {
        source: 'Plan',
        excerpt: 'albuterol HFA 2 puffs Q4H PRN',
        rationale: 'Standard short-acting bronchodilator therapy supports J45.40 (moderate persistent, uncomplicated).',
      },
    ];
  }
  return [
    {
      source: 'Subjective',
      excerpt: 'patient-reported symptoms align with the selected code\'s clinical presentation',
      rationale: 'Top-ranked semantic match against ICD-10 description embeddings.',
    },
    {
      source: 'Objective',
      excerpt: 'documented vitals + exam findings reinforce the diagnostic category',
      rationale: 'Cross-checked against ICD-10 category typical findings.',
    },
    {
      source: 'Assessment',
      excerpt: 'physician notes corroborate this differential',
      rationale: 'Highest cosine similarity in coded knowledge base.',
    },
  ];
}

/**
 * Host component — render once in the layout. The drawer renders into a portal-like
 * fixed overlay and is controlled by the global Zustand store.
 */
export const ICDReasoningDrawerHost: React.FC = () => {
  const { isOpen, payload, close } = useDrawerStore();
  const [render, setRender] = useState(false);

  // Mount/unmount with transition
  useEffect(() => {
    if (isOpen) setRender(true);
    else {
      const t = setTimeout(() => setRender(false), 220);
      return () => clearTimeout(t);
    }
  }, [isOpen]);

  useEscapeKey(close, isOpen);

  if (!render || !payload) return null;

  const citations = payload.citations ?? mockCitations(payload.code);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="icd-reason-title"
      className="fixed inset-0 z-[55] flex justify-end"
    >
      {/* Backdrop */}
      <div
        className={clsx(
          'absolute inset-0 bg-black/50 backdrop-blur-sm transition-opacity duration-200',
          isOpen ? 'opacity-100' : 'opacity-0'
        )}
        onClick={close}
        aria-hidden="true"
      />

      {/* Panel */}
      <aside
        className={clsx(
          'relative h-full w-full max-w-md',
          'bg-primary-900 border-l border-primary-700 shadow-2xl',
          'flex flex-col',
          'transition-transform duration-200 ease-out',
          isOpen ? 'translate-x-0' : 'translate-x-full'
        )}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3 p-5 border-b border-primary-700">
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-wider text-teal-400 font-semibold mb-1">
              AI Reasoning
            </p>
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-xl font-bold text-teal-300">{payload.code}</span>
              <ConfidencePill value={payload.confidence} size="sm" />
            </div>
            <h2
              id="icd-reason-title"
              className="text-sm text-gray-200 mt-1.5 leading-snug"
            >
              {payload.description}
            </h2>
            {payload.category && (
              <p className="text-xs text-gray-500 mt-1">{payload.category}</p>
            )}
          </div>
          <button
            onClick={close}
            aria-label="Close ICD reasoning drawer"
            className="shrink-0 p-2 rounded-lg text-gray-400 hover:text-white hover:bg-primary-800 min-h-[40px] min-w-[40px] flex items-center justify-center"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          <section>
            <h3 className="text-xs uppercase tracking-wider text-gray-400 font-semibold mb-3 flex items-center gap-2">
              <svg className="h-3.5 w-3.5 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Why this code?
            </h3>
            <ul className="space-y-3">
              {citations.map((c, i) => (
                <li
                  key={i}
                  className="rounded-lg border border-primary-700 bg-primary-800/40 p-3"
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="inline-flex h-5 items-center px-2 rounded-md bg-teal-900/40 border border-teal-700/50 text-[10px] font-semibold uppercase tracking-wider text-teal-300">
                      {c.source}
                    </span>
                  </div>
                  <p className="text-xs italic text-gray-300 leading-snug">
                    &ldquo;{c.excerpt}&rdquo;
                  </p>
                  <p className="text-xs text-gray-400 mt-1.5 leading-snug">
                    → {c.rationale}
                  </p>
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded-lg border border-primary-700 bg-primary-800/30 p-3">
            <p className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold mb-1">
              Disclaimer
            </p>
            <p className="text-xs text-gray-400 leading-snug">
              AI reasoning is provided to assist clinical decision-making.
              The physician of record is responsible for final coding accuracy.
            </p>
          </section>
        </div>
      </aside>
    </div>
  );
};
