/**
 * LoginPage for ClinNote AI
 *
 * Email/password + optional TOTP MFA login form.
 * Tablet-optimized layout with large touch targets.
 */

import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useLocation, Link } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/atoms/Button';
import { Input } from '@/components/atoms/Input';
import type { APIError } from '@/types/api';

const loginSchema = z.object({
  email: z.string().email('Please enter a valid email'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
});

const mfaSchema = z.object({
  code: z
    .string()
    .length(6, 'TOTP code must be 6 digits')
    .regex(/^\d+$/, 'Code must be numeric'),
});

type LoginFormData = z.infer<typeof loginSchema>;
type MFAFormData = z.infer<typeof mfaSchema>;

/**
 * Clinical Login Page
 */
export const LoginPage: React.FC = () => {
  const { login, verifyMFA, mfaRequired } = useAuth();
  const location = useLocation();
  const sessionExpired = (location.state as { reason?: string })?.reason === 'inactivity';

  const [apiError, setApiError] = useState<string | null>(null);

  const loginForm = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  });

  const mfaForm = useForm<MFAFormData>({
    resolver: zodResolver(mfaSchema),
  });

  const handleLogin = async (data: LoginFormData) => {
    setApiError(null);
    try {
      await login(data);
    } catch (error) {
      const apiErr = error as APIError;
      if (apiErr.status === 401) {
        setApiError('Invalid email or password. Please try again.');
      } else {
        setApiError(apiErr.message ?? 'Login failed. Please check your credentials.');
      }
    }
  };

  const handleMFA = async (data: MFAFormData) => {
    setApiError(null);
    try {
      await verifyMFA(data.code);
    } catch (error) {
      const apiErr = error as APIError;
      setApiError(apiErr.message ?? 'Invalid verification code. Please try again.');
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
      {/* Background pattern */}
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

        {/* Session expired notice */}
        {sessionExpired && (
          <div
            role="alert"
            className="mb-4 flex items-center gap-2 rounded-lg bg-amber-900/30 border border-amber-700 px-4 py-3"
          >
            <svg className="h-4 w-4 text-amber-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <p className="text-sm text-amber-300">
              Your session expired due to inactivity. Please sign in again.
            </p>
          </div>
        )}

        {/* Login form card */}
        <div className="rounded-2xl bg-primary-900 border border-primary-700 p-8 shadow-2xl">
          {!mfaRequired ? (
            <>
              <h2 className="text-xl font-semibold text-white mb-6">Sign In</h2>

              <form
                onSubmit={loginForm.handleSubmit(handleLogin)}
                noValidate
                className="space-y-4"
              >
                <Input
                  label="Email Address"
                  type="email"
                  autoComplete="email"
                  placeholder="physician@hospital.org"
                  required
                  error={loginForm.formState.errors.email?.message}
                  leftIcon={
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207" />
                    </svg>
                  }
                  {...loginForm.register('email')}
                />

                <Input
                  label="Password"
                  type="password"
                  autoComplete="current-password"
                  placeholder="••••••••••"
                  required
                  error={loginForm.formState.errors.password?.message}
                  leftIcon={
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                    </svg>
                  }
                  {...loginForm.register('password')}
                />

                {/* API error */}
                {apiError && (
                  <div role="alert" className="flex items-center gap-2 rounded-lg bg-red-900/30 border border-red-700 px-3 py-2.5">
                    <svg className="h-4 w-4 text-red-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <p className="text-sm text-red-300">{apiError}</p>
                  </div>
                )}

                {/* Forgot password link */}
                <div className="flex justify-end">
                  <Link
                    to="/forgot-password"
                    className="text-xs text-teal-400 hover:text-teal-300 transition-colors focus:outline-2 focus:outline-offset-2 focus:outline-teal-400 rounded"
                  >
                    Forgot password?
                  </Link>
                </div>

                <Button
                  type="submit"
                  variant="primary"
                  size="xl"
                  fullWidth
                  loading={loginForm.formState.isSubmitting}
                  className="mt-6"
                >
                  Sign In
                </Button>
              </form>
            </>
          ) : (
            <>
              <div className="flex items-center gap-3 mb-6">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-700">
                  <svg className="h-5 w-5 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" />
                  </svg>
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-white">Two-Factor Authentication</h2>
                  <p className="text-sm text-gray-400">Enter the code from your authenticator app</p>
                </div>
              </div>

              <form
                onSubmit={mfaForm.handleSubmit(handleMFA)}
                noValidate
                className="space-y-4"
              >
                <Input
                  key="mfa-code-input"
                  label="Verification Code"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={6}
                  placeholder="000000"
                  required
                  error={mfaForm.formState.errors.code?.message}
                  className="text-center text-2xl tracking-widest font-mono"
                  {...mfaForm.register('code')}
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
                  loading={mfaForm.formState.isSubmitting}
                  className="mt-6"
                >
                  Verify
                </Button>
              </form>
            </>
          )}
        </div>

        {/* HIPAA notice */}
        <p className="text-center text-xs text-gray-600 mt-4">
          This system contains protected health information (PHI).
          Unauthorized access is prohibited per HIPAA regulations.
        </p>
      </div>
    </div>
  );
};
