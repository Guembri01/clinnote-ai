/**
 * ForgotPasswordPage for ClinNote AI
 *
 * Collects user email and shows a confirmation message once submitted.
 * Backend sends a password-reset link to the provided email.
 */

import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from '@/components/atoms/Button';
import { Input } from '@/components/atoms/Input';

const schema = z.object({
  email: z.string().email('Please enter a valid email address'),
});

type FormData = z.infer<typeof schema>;

/**
 * Forgot Password Page
 */
export const ForgotPasswordPage: React.FC = () => {
  const [submitted, setSubmitted] = useState(false);
  const [submittedEmail, setSubmittedEmail] = useState('');
  const [apiError, setApiError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const onSubmit = async (data: FormData) => {
    setApiError(null);
    try {
      // POST to backend reset endpoint; silently succeed even if email unknown
      await fetch('/api/v1/auth/password-reset/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: data.email }),
      });
      setSubmittedEmail(data.email);
      setSubmitted(true);
    } catch {
      setApiError('Unable to send reset email. Please try again later.');
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
      {/* Background blobs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden="true">
        <div className="absolute -top-1/2 -left-1/4 w-96 h-96 bg-primary-900/20 rounded-full blur-3xl" />
        <div className="absolute -bottom-1/4 -right-1/4 w-96 h-96 bg-teal-900/10 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <img
            src="/icons/medical-cross.svg"
            alt="ClinNote AI"
            className="h-16 w-16 rounded-2xl mb-4"
          />
          <h1 className="text-2xl font-bold text-white">ClinNote AI</h1>
          <p className="text-sm text-gray-400 mt-1">Ambient Clinical Documentation</p>
        </div>

        <div className="rounded-2xl bg-primary-900 border border-primary-700 p-8 shadow-2xl">
          {!submitted ? (
            <>
              {/* Header */}
              <div className="flex items-center gap-3 mb-6">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-700">
                  <svg
                    className="h-5 w-5 text-teal-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    aria-hidden="true"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"
                    />
                  </svg>
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-white">Reset Password</h2>
                  <p className="text-sm text-gray-400">Enter your account email to receive a reset link</p>
                </div>
              </div>

              <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
                <Input
                  label="Email Address"
                  type="email"
                  autoComplete="email"
                  placeholder="physician@hospital.org"
                  required
                  error={errors.email?.message}
                  leftIcon={
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207" />
                    </svg>
                  }
                  {...register('email')}
                />

                {apiError && (
                  <div role="alert" className="flex items-center gap-2 rounded-lg bg-red-900/30 border border-red-700 px-3 py-2.5">
                    <svg className="h-4 w-4 text-red-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <p className="text-sm text-red-300">{apiError}</p>
                  </div>
                )}

                <Button
                  type="submit"
                  variant="primary"
                  size="xl"
                  fullWidth
                  loading={isSubmitting}
                  className="mt-6"
                >
                  Send Reset Link
                </Button>
              </form>
            </>
          ) : (
            /* Confirmation state */
            <div className="flex flex-col items-center text-center gap-4 py-2">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-teal-900/50 border border-teal-600">
                <svg className="h-7 w-7 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
              <div>
                <h2 className="text-xl font-semibold text-white">Check Your Inbox</h2>
                <p className="text-sm text-gray-400 mt-2">
                  If an account exists for{' '}
                  <span className="text-teal-300 font-medium">{submittedEmail}</span>
                  , a password reset link has been sent.
                </p>
                <p className="text-xs text-gray-500 mt-3">
                  Didn&apos;t receive it? Check your spam folder or contact your system administrator.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Back to login */}
        <div className="mt-4 text-center">
          <Link
            to="/login"
            className="text-sm text-teal-400 hover:text-teal-300 transition-colors focus:outline-2 focus:outline-offset-2 focus:outline-teal-400 rounded"
          >
            &larr; Back to Sign In
          </Link>
        </div>

        <p className="text-center text-xs text-gray-600 mt-4">
          This system contains protected health information (PHI).
          Unauthorized access is prohibited per HIPAA regulations.
        </p>
      </div>
    </div>
  );
};
