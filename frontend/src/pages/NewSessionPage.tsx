/**
 * NewSessionPage for ClinNote AI
 *
 * 5-step wizard:
 * 1. Patient information
 * 2. Lab report upload (optional)
 * 3. Patient consent
 * 4. Recording interface
 * 5. Redirect to ReviewNotePage
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useMutation } from '@tanstack/react-query';
import { startRecording as createRecordingSession } from '@/api/recordings';
import { generateNote } from '@/api/notes';
import { ConsentModal } from '@/components/molecules/ConsentModal';
import { LabReportUpload } from '@/components/molecules/LabReportUpload';
import { RecordingInterface } from '@/components/organisms/RecordingInterface';
import { Button } from '@/components/atoms/Button';
import { Input } from '@/components/atoms/Input';
import { useToast } from '@/components/atoms/Toast';
import type { PatientInfo, ConsentLanguage } from '@/types/recording';
import type { UploadedDocument } from '@/api/documents';
import type { RecordingSession } from '@/types/recording';

type Step = 1 | 2 | 3 | 4 | 5;

const patientSchema = z.object({
  mrn: z.string().min(1, 'MRN is required'),
  first_name: z.string().min(1, 'First name is required'),
  last_name: z.string().min(1, 'Last name is required'),
  date_of_birth: z.string().min(1, 'Date of birth is required'),
  encounter_id: z.string().min(1, 'Encounter ID is required'),
  chief_complaint: z.string().optional(),
});

type PatientFormData = z.infer<typeof patientSchema>;

const STEP_LABELS: Record<Step, string> = {
  1: 'Patient Info',
  2: 'Lab Reports',
  3: 'Consent',
  4: 'Recording',
  5: 'Processing',
};

/**
 * New Session Wizard Page
 */
export const NewSessionPage: React.FC = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [step, setStep] = useState<Step>(1);
  const [patientData, setPatientData] = useState<PatientInfo | null>(null);
  const [uploadedDocs, setUploadedDocs] = useState<UploadedDocument[]>([]);
  const [session, setSession] = useState<RecordingSession | null>(null);
  const [showConsentModal, setShowConsentModal] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { handleSubmit, register, formState: { errors, isSubmitting } } = useForm<PatientFormData>({
    resolver: zodResolver(patientSchema),
  });

  const { mutateAsync: createSession } = useMutation({
    mutationFn: createRecordingSession,
  });

  // Screenshot helper: when navigating with ?step=5&screenshot=1, jump straight
  // to the AI generation progress screen so it can be captured deterministically.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    if (params.get('screenshot') === '1' && params.get('step') === '5') {
      setStep(5);
    }
  }, []);

  // Step 1: Submit patient info
  const onPatientSubmit = (data: PatientFormData) => {
    setPatientData(data as PatientInfo);
    setStep(2);
  };

  // Step 2 → 3: Proceed to consent
  const handleLabsDone = () => {
    setShowConsentModal(true);
  };

  // Step 3: Consent obtained
  const handleConsent = async (language: ConsentLanguage) => {
    setShowConsentModal(false);
    setError(null);

    if (!patientData) return;

    try {
      const newSession = await createSession({
        patient: patientData,
        consent: {
          consented: true,
          language,
          timestamp: new Date().toISOString(),
          method: 'verbal',
          recorded_by: 'physician',
        },
        lab_document_ids: uploadedDocs.map((d) => d.id),
      });

      setSession(newSession);
      setStep(4);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start session');
    }
  };

  const handleEmergencyConsent = async () => {
    setShowConsentModal(false);
    setError(null);

    if (!patientData) return;

    try {
      const newSession = await createSession({
        patient: patientData,
        consent: {
          consented: true,
          language: 'en',
          timestamp: new Date().toISOString(),
          method: 'emergency_exception',
          recorded_by: 'physician',
        },
        lab_document_ids: uploadedDocs.map((d) => d.id),
      });

      setSession(newSession);
      setStep(4);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start session');
    }
  };

  const handleDeclineConsent = () => {
    setShowConsentModal(false);
    setError('Patient declined consent. Recording cannot proceed.');
  };

  // Step 4 → 5: Recording done, navigate to review
  const handleNoteReady = async (_transcriptId: string) => {
    setStep(5);
    if (!session) return;

    try {
      const note = await generateNote(session.id);
      toast.success('SOAP note generated successfully. Redirecting to review...');
      navigate(`/notes/${note.id}/review`, { replace: true });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to generate note';
      setError(msg);
      toast.error(`Note generation failed: ${msg}`);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">New Session</h1>
        <p className="text-gray-400 text-sm mt-1">Start a new clinical recording session</p>
      </div>

      {/* Step indicator */}
      <div className="flex items-center gap-2" role="list" aria-label="Session setup steps">
        {([1, 2, 3, 4] as Step[]).map((s) => (
          <React.Fragment key={s}>
            <div
              role="listitem"
              aria-current={step === s ? 'step' : undefined}
              className="flex items-center gap-2"
            >
              <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold transition-colors ${
                step > s
                  ? 'bg-teal-600 text-white'
                  : step === s
                  ? 'bg-primary-500 text-white'
                  : 'bg-primary-800 text-gray-400'
              }`}>
                {step > s ? (
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                ) : s}
              </div>
              <span className={`text-xs hidden tablet:block ${step === s ? 'text-gray-200' : step > s ? 'text-teal-400' : 'text-gray-500'}`}>
                {STEP_LABELS[s]}
              </span>
            </div>
            {s < 4 && (
              <div className={`flex-1 h-px transition-colors ${step > s ? 'bg-teal-600' : 'bg-primary-700'}`} aria-hidden="true" />
            )}
          </React.Fragment>
        ))}
      </div>

      {/* Error display */}
      {error && (
        <div role="alert" className="rounded-lg bg-red-900/30 border border-red-700 p-4 flex items-start gap-2">
          <svg className="h-4 w-4 text-red-400 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div>
            <p className="text-sm font-medium text-red-300">Error</p>
            <p className="text-xs text-red-400">{error}</p>
          </div>
          <button onClick={() => setError(null)} className="ml-auto text-gray-500 hover:text-gray-300 min-h-[32px] min-w-[32px] flex items-center justify-center">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      {/* Step 1: Patient Info */}
      {step === 1 && (
        <div className="rounded-xl border border-primary-700 bg-primary-900/30 p-6 space-y-5">
          <h2 className="text-lg font-semibold text-white">Patient Information</h2>

          <form onSubmit={handleSubmit(onPatientSubmit)} noValidate className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <Input
                label="First Name"
                placeholder="Patient first name"
                required
                error={errors.first_name?.message}
                {...register('first_name')}
              />
              <Input
                label="Last Name"
                placeholder="Patient last name"
                required
                error={errors.last_name?.message}
                {...register('last_name')}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Input
                label="MRN"
                placeholder="MRN-XXXXXX"
                required
                error={errors.mrn?.message}
                {...register('mrn')}
              />
              <Input
                label="Date of Birth"
                type="date"
                required
                error={errors.date_of_birth?.message}
                {...register('date_of_birth')}
              />
            </div>

            <Input
              label="Encounter ID"
              placeholder="ENC-YYYY-NNNN"
              required
              error={errors.encounter_id?.message}
              {...register('encounter_id')}
            />

            <Input
              label="Chief Complaint (optional)"
              placeholder="e.g. chest pain × 2 days, worse with exertion"
              {...register('chief_complaint')}
            />

            <Button
              type="submit"
              variant="primary"
              size="lg"
              fullWidth
              loading={isSubmitting}
              className="mt-2"
            >
              Continue
            </Button>
          </form>
        </div>
      )}

      {/* Step 2: Lab Reports */}
      {step === 2 && (
        <div className="rounded-xl border border-primary-700 bg-primary-900/30 p-6 space-y-5">
          <div>
            <h2 className="text-lg font-semibold text-white">Lab Reports</h2>
            <p className="text-sm text-gray-400 mt-1">Upload relevant lab reports (optional — helps AI improve accuracy)</p>
          </div>

          <LabReportUpload
            onUpload={(doc) => setUploadedDocs((prev) => [...prev, doc])}
            onRemove={(id) => setUploadedDocs((prev) => prev.filter((d) => d.id !== id))}
            uploadedDocuments={uploadedDocs}
          />

          <div className="flex gap-3 pt-2">
            <Button variant="ghost" size="lg" onClick={() => setStep(1)}>
              Back
            </Button>
            <Button
              variant="primary"
              size="lg"
              fullWidth
              onClick={handleLabsDone}
            >
              {uploadedDocs.length > 0
                ? `Continue with ${uploadedDocs.length} file${uploadedDocs.length > 1 ? 's' : ''}`
                : 'Continue without uploads'}
            </Button>
          </div>
        </div>
      )}

      {/* Step 3: Consent (handled via modal) */}
      {step === 3 && (
        <div className="rounded-xl border border-primary-700 bg-primary-900/30 p-6 text-center space-y-4">
          <p className="text-gray-300">Waiting for patient consent...</p>
          <Button variant="ghost" size="md" onClick={() => { setStep(2); setShowConsentModal(false); }}>
            Back
          </Button>
        </div>
      )}

      {/* Step 4: Recording */}
      {step === 4 && session && patientData && (
        <div className="rounded-xl border border-primary-700 bg-primary-900/30 p-6">
          <RecordingInterface
            sessionId={session.id}
            patient={patientData}
            onNoteReady={handleNoteReady}
            onCancel={() => navigate('/dashboard')}
          />
        </div>
      )}

      {/* Step 5: Processing — AI note generation progress */}
      {step === 5 && <NoteGenerationScreen />}

      {/* Consent Modal */}
      <ConsentModal
        isOpen={showConsentModal}
        onConsent={handleConsent}
        onDecline={handleDeclineConsent}
        onEmergency={handleEmergencyConsent}
        patientName={patientData ? `${patientData.first_name} ${patientData.last_name}` : undefined}
      />
    </div>
  );
};

const AI_STEPS = [
  { label: 'Transcribing audio...', icon: '🎙️', duration: 2500 },
  { label: 'Extracting clinical entities...', icon: '🔍', duration: 2000 },
  { label: 'Generating SOAP note...', icon: '📝', duration: 2500 },
  { label: 'Coding diagnoses (ICD-10 / CPT)...', icon: '🏥', duration: 2000 },
  { label: 'Reviewing clinical accuracy...', icon: '✅', duration: 1500 },
];

/**
 * AI Note Generation Progress Screen
 * Shows step-by-step progress between recording stop and note review.
 */
const NoteGenerationScreen: React.FC = () => {
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    let idx = 0;
    const advance = () => {
      idx += 1;
      if (idx < AI_STEPS.length) {
        setCurrentStep(idx);
        setTimeout(advance, AI_STEPS[idx].duration);
      }
    };
    const t = setTimeout(advance, AI_STEPS[0].duration);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="rounded-xl border border-primary-700 bg-primary-900/30 p-10 flex flex-col items-center gap-8">
      {/* Animated AI brain icon */}
      <div className="relative flex items-center justify-center h-20 w-20">
        <div className="absolute inset-0 rounded-full bg-teal-500/10 animate-ping" aria-hidden="true" />
        <div className="relative flex h-20 w-20 items-center justify-center rounded-full bg-teal-900/60 border-2 border-teal-500 shadow-lg shadow-teal-500/20">
          <svg className="h-10 w-10 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
        </div>
      </div>

      <div className="text-center space-y-1">
        <p className="text-xl font-semibold text-white">Generating Your Note</p>
        <p className="text-sm text-gray-400">AI is analyzing the recording and creating your SOAP note</p>
      </div>

      {/* AI processing steps */}
      <div className="w-full max-w-sm space-y-3">
        {AI_STEPS.map((step, idx) => {
          const isDone = idx < currentStep;
          const isActive = idx === currentStep;
          return (
            <div
              key={idx}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-500 ${
                isActive
                  ? 'bg-teal-900/30 border border-teal-700'
                  : isDone
                  ? 'bg-green-900/20 border border-green-800/40'
                  : 'border border-transparent opacity-40'
              }`}
            >
              {isDone ? (
                <svg className="h-5 w-5 text-green-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
              ) : isActive ? (
                <div className="h-5 w-5 rounded-full border-2 border-teal-400 border-t-transparent animate-spin shrink-0" aria-hidden="true" />
              ) : (
                <div className="h-5 w-5 rounded-full border-2 border-gray-600 shrink-0" aria-hidden="true" />
              )}
              <p className={`text-sm font-medium ${isActive ? 'text-teal-300' : isDone ? 'text-green-400' : 'text-gray-500'}`}>
                {step.label}
              </p>
            </div>
          );
        })}
      </div>

      {/* AI processing indicator — animated thinking dots */}
      <div className="flex items-center gap-2 text-teal-400">
        <span className="ai-thinking-dot" aria-hidden="true" />
        <span className="ai-thinking-dot" aria-hidden="true" />
        <span className="ai-thinking-dot" aria-hidden="true" />
        <span className="text-sm ml-1 font-medium">AI is analyzing your consultation...</span>
      </div>
    </div>
  );
};
