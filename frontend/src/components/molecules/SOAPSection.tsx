/**
 * SOAPSection molecule for ClinNote AI
 *
 * Editable SOAP note section with AI-generated vs. physician-edited diff visualization.
 *
 * @example
 * <SOAPSection
 *   type="subjective"
 *   section={note.sections.subjective}
 *   onChange={(text) => editSection('subjective', text)}
 * />
 */

import React, { useState, useRef, useEffect } from 'react';
import { clsx } from 'clsx';
import type { SOAPSection as SOAPSectionType, SOAPSectionType as SectionType } from '@/types/soap';
import { diffTexts } from '@/utils/diffUtils';
import { Badge } from '@/components/atoms/Badge';
import { useTypewriter } from '@/hooks/useTypewriter';

export interface SOAPSectionProps {
  /** Section type */
  type: SectionType;
  /** Section data */
  section: SOAPSectionType;
  /** Called when text changes */
  onChange: (text: string) => void;
  /** Whether the section is in view-only mode */
  readOnly?: boolean;
  /** Whether to show the diff view */
  showDiff?: boolean;
}

const sectionMeta: Record<SectionType, { label: string; description: string; icon: string }> = {
  subjective: {
    label: 'Subjective',
    description: "Patient's reported symptoms, history, complaints",
    icon: 'S',
  },
  objective: {
    label: 'Objective',
    description: 'Vital signs, exam findings, lab results',
    icon: 'O',
  },
  assessment: {
    label: 'Assessment',
    description: 'Diagnosis and clinical reasoning',
    icon: 'A',
  },
  plan: {
    label: 'Plan',
    description: 'Treatment plan, medications, follow-up',
    icon: 'P',
  },
};

/**
 * Renders SOAP note text as structured HTML.
 * Handles numbered lists, bullet lists, bold headers (**text**), and line breaks.
 */
function renderStructuredContent(text: string): React.ReactNode {
  const lines = text.split('\n');
  const nodes: React.ReactNode[] = [];
  let listItems: string[] = [];
  let listType: 'ol' | 'ul' | null = null;

  const flushList = (key: string) => {
    if (listItems.length === 0) return;
    if (listType === 'ol') {
      nodes.push(
        <ol key={key} className="list-decimal list-inside space-y-1 pl-2">
          {listItems.map((item, i) => (
            <li key={i} className="text-gray-200">{renderInline(item)}</li>
          ))}
        </ol>
      );
    } else {
      nodes.push(
        <ul key={key} className="list-disc list-inside space-y-1 pl-2">
          {listItems.map((item, i) => (
            <li key={i} className="text-gray-200">{renderInline(item)}</li>
          ))}
        </ul>
      );
    }
    listItems = [];
    listType = null;
  };

  lines.forEach((line, idx) => {
    const numberedMatch = line.match(/^(\d+)\.\s+(.+)/);
    const bulletMatch = line.match(/^[-*•]\s+(.+)/);

    if (numberedMatch) {
      if (listType && listType !== 'ol') flushList(`flush-${idx}`);
      listType = 'ol';
      listItems.push(numberedMatch[2]);
    } else if (bulletMatch) {
      if (listType && listType !== 'ul') flushList(`flush-${idx}`);
      listType = 'ul';
      listItems.push(bulletMatch[1]);
    } else {
      flushList(`flush-${idx}`);
      if (line.trim() === '') {
        nodes.push(<div key={idx} className="h-1" />);
      } else {
        nodes.push(
          <p key={idx} className="text-gray-200">{renderInline(line)}</p>
        );
      }
    }
  });

  flushList('final');
  return <>{nodes}</>;
}

/**
 * Renders inline markdown: **bold**, `code`, and plain text.
 */
function renderInline(text: string): React.ReactNode {
  // Split on **bold** and `code` patterns
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-semibold text-white">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code key={i} className="font-mono text-xs bg-primary-800 text-teal-300 px-1 py-0.5 rounded">
          {part.slice(1, -1)}
        </code>
      );
    }
    return part;
  });
}

/**
 * Editable SOAP Note Section
 */
export const SOAPSection: React.FC<SOAPSectionProps> = ({
  type,
  section,
  onChange,
  readOnly = false,
  showDiff = false,
}) => {
  const meta = sectionMeta[type];
  const currentText = section.physician_edited_text ?? section.ai_generated_text;
  const [isExpanded, setIsExpanded] = useState(true);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Typewriter reveal for AI-generated content (read-only or freshly generated).
  // We animate only the AI text, not the physician-edited text.
  const showTypewriter = readOnly && !section.is_modified;
  const typedText = useTypewriter(showTypewriter ? currentText : '', {
    disabled: !showTypewriter,
  });

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, [currentText]);

  const diffSegments = showDiff && section.is_modified
    ? diffTexts(section.ai_generated_text, section.physician_edited_text ?? '')
    : null;

  return (
    <section
      aria-label={`${meta.label} section`}
      className="rounded-xl border border-primary-700 bg-primary-900/30 overflow-hidden"
    >
      {/* Section header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        aria-expanded={isExpanded}
        className={clsx(
          'w-full flex items-center justify-between px-4 py-3',
          'bg-primary-800/50 hover:bg-primary-800 transition-colors',
          'min-h-[52px] text-left'
        )}
      >
        <div className="flex items-center gap-3">
          <span
            className="flex items-center justify-center h-7 w-7 rounded-lg bg-teal-600/30 text-teal-300 font-bold text-sm"
            aria-hidden="true"
          >
            {meta.icon}
          </span>
          <div>
            <h3 className="text-sm font-semibold text-gray-100">{meta.label}</h3>
            <p className="text-xs text-gray-500">{meta.description}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {section.is_modified && (
            <Badge variant="warning" size="sm">Edited</Badge>
          )}
          {!section.is_modified && (
            <Badge variant="teal" size="sm">AI Generated</Badge>
          )}
          <svg
            className={clsx('h-4 w-4 text-gray-400 transition-transform', !isExpanded && 'rotate-180')}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
          </svg>
        </div>
      </button>

      {/* Section content */}
      {isExpanded && (
        <div className="p-4">
          {showDiff && diffSegments ? (
            /* Diff view */
            <div className="text-sm leading-relaxed font-mono bg-gray-950/50 rounded-lg p-3">
              {diffSegments.map((seg, i) => (
                <span
                  key={i}
                  className={clsx(
                    seg.type === 'added' && 'bg-green-900/40 text-green-300 rounded px-0.5',
                    seg.type === 'removed' && 'bg-red-900/40 text-red-300 line-through rounded px-0.5',
                    seg.type === 'equal' && 'text-gray-300'
                  )}
                >
                  {seg.text}
                </span>
              ))}
            </div>
          ) : readOnly ? (
            /* Read-only view with structured markdown rendering + typewriter reveal */
            <div className="text-sm text-gray-200 leading-[1.75] space-y-2 px-1 py-1">
              {currentText ? (
                showTypewriter ? (
                  // Animate AI text in
                  <div className="relative">
                    {renderStructuredContent(typedText || '')}
                    {typedText.length < currentText.length && (
                      <span
                        className="inline-block w-[2px] h-4 ml-0.5 bg-teal-400 align-middle animate-pulse"
                        aria-hidden="true"
                      />
                    )}
                  </div>
                ) : (
                  renderStructuredContent(currentText)
                )
              ) : (
                <span className="text-gray-500 italic">No content</span>
              )}
            </div>
          ) : (
            /* Editable textarea */
            <div className="relative">
              <textarea
                ref={textareaRef}
                value={currentText}
                onChange={(e) => onChange(e.target.value)}
                aria-label={`Edit ${meta.label} section`}
                className={clsx(
                  'w-full bg-transparent text-sm text-gray-100 leading-relaxed',
                  'resize-none outline-none',
                  'placeholder-gray-600',
                  'rounded-lg p-3',
                  'border border-transparent',
                  'hover:border-primary-600 focus:border-teal-500',
                  'transition-colors duration-150',
                  'focus:bg-primary-950/50'
                )}
                placeholder={`Enter ${meta.label.toLowerCase()} findings...`}
                style={{ minHeight: '100px' }}
              />
              {!section.is_modified && (
                <span className="absolute top-3 right-3 text-xs text-teal-500/60 pointer-events-none">
                  AI
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
};
