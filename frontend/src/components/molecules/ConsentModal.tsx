/**
 * ConsentModal molecule for ClinNote AI
 *
 * Patient consent dialog with multilingual support (EN/ES/FR).
 * Consent cannot be skipped unless it's an emergency encounter.
 *
 * @example
 * <ConsentModal
 *   isOpen={showConsent}
 *   onConsent={(language) => handleConsent(language)}
 *   onDecline={() => handleDecline()}
 *   onEmergency={() => handleEmergencyException()}
 * />
 */

import React, { useState } from 'react';
import { clsx } from 'clsx';
import { Button } from '@/components/atoms/Button';
import { useEscapeKey } from '@/hooks/useEscapeKey';
import type { ConsentLanguage } from '@/types/recording';

export interface ConsentModalProps {
  /** Whether the modal is visible */
  isOpen: boolean;
  /** Called when patient consents */
  onConsent: (language: ConsentLanguage) => void;
  /** Called when patient declines */
  onDecline: () => void;
  /** Called for emergency exception */
  onEmergency: () => void;
  /** Patient name for personalized consent */
  patientName?: string;
}

const consentTexts: Record<ConsentLanguage, { title: string; body: string; consent: string; decline: string }> = {
  en: {
    title: 'Recording Consent',
    body: 'This consultation will be recorded using ambient AI technology for the purpose of generating clinical documentation. The recording will be processed securely and used only for your medical record. Do you consent to this recording?',
    consent: 'Patient Consents',
    decline: 'Patient Declines',
  },
  es: {
    title: 'Consentimiento de Grabación',
    body: 'Esta consulta será grabada utilizando tecnología de IA ambiental con el propósito de generar documentación clínica. La grabación se procesará de forma segura y se utilizará únicamente para su historial médico. ¿Da su consentimiento para esta grabación?',
    consent: 'Paciente Consiente',
    decline: 'Paciente Rechaza',
  },
  fr: {
    title: 'Consentement d\'Enregistrement',
    body: 'Cette consultation sera enregistrée à l\'aide de la technologie d\'IA ambiante afin de générer une documentation clinique. L\'enregistrement sera traité de manière sécurisée et utilisé uniquement pour votre dossier médical. Consentez-vous à cet enregistrement?',
    consent: 'Patient Consent',
    decline: 'Patient Refuse',
  },
};

const languageLabels: Record<ConsentLanguage, string> = {
  en: 'English',
  es: 'Español',
  fr: 'Français',
};

/**
 * Patient Consent Modal
 */
export const ConsentModal: React.FC<ConsentModalProps> = ({
  isOpen,
  onConsent,
  onDecline,
  onEmergency,
  patientName,
}) => {
  const [language, setLanguage] = useState<ConsentLanguage>('en');

  // Escape dismisses consent as "decline" — safest default for HIPAA.
  useEscapeKey(onDecline, isOpen);

  if (!isOpen) return null;

  const text = consentTexts[language];

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="consent-title"
      aria-describedby="consent-body"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" aria-hidden="true" />

      {/* Modal */}
      <div className="relative w-full max-w-lg rounded-2xl bg-primary-900 border border-primary-600 shadow-2xl animate-slide-in-up">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-primary-700">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-700">
              <svg className="h-5 w-5 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
            <div>
              <h2 id="consent-title" className="text-lg font-semibold text-white">
                {text.title}
              </h2>
              {patientName && (
                <p className="text-sm text-gray-400">Patient: {patientName}</p>
              )}
            </div>
          </div>

          {/* Language selector */}
          <div className="flex gap-1" role="group" aria-label="Select consent language">
            {(Object.keys(languageLabels) as ConsentLanguage[]).map((lang) => (
              <button
                key={lang}
                onClick={() => setLanguage(lang)}
                aria-pressed={language === lang}
                className={clsx(
                  'px-2.5 py-1.5 text-xs font-medium rounded-lg transition-colors min-h-[36px]',
                  language === lang
                    ? 'bg-teal-600 text-white'
                    : 'text-gray-400 hover:text-white hover:bg-primary-700'
                )}
              >
                {lang.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {/* Body */}
        <div className="p-6">
          <p id="consent-body" className="text-gray-200 text-base leading-relaxed">
            {text.body}
          </p>

          <div className="mt-4 rounded-lg bg-primary-800/50 border border-primary-700 p-3">
            <p className="text-xs text-gray-400 flex items-start gap-2">
              <svg className="h-4 w-4 text-teal-500 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
              Recordings are encrypted at rest and in transit. Access is restricted to authorized clinical staff only per HIPAA regulations.
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="p-6 pt-0 space-y-3">
          {/* Primary consent button */}
          <Button
            variant="success"
            size="xl"
            fullWidth
            onClick={() => onConsent(language)}
            aria-label={`${text.consent} in ${languageLabels[language]}`}
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
            </svg>
            {text.consent}
          </Button>

          <div className="flex gap-3">
            {/* Decline button */}
            <Button
              variant="ghost"
              size="md"
              fullWidth
              onClick={onDecline}
              aria-label={text.decline}
            >
              {text.decline}
            </Button>

            {/* Emergency exception */}
            <button
              onClick={onEmergency}
              className={clsx(
                'flex-1 px-4 py-2 text-sm text-amber-400 hover:text-amber-300',
                'border border-amber-800/50 hover:border-amber-700 rounded-lg',
                'transition-colors min-h-[44px]',
                'flex items-center justify-center gap-1.5'
              )}
              aria-label="Skip consent — Emergency encounter"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              Emergency
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
