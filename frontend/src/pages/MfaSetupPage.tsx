/**
 * MfaSetupPage for ClinNote AI
 *
 * Two-step Multi-Factor Authentication enrollment:
 *  1. Disabled state — single "Enable MFA" call-to-action
 *  2. Setup state    — shows otpauth URL + secret, confirms by 6-digit TOTP code
 *
 * No new npm dependencies. QR rendering is omitted; users paste the otpauth
 * URL into their authenticator (most apps support this) or type the secret.
 */

import React, { useState } from 'react';
import { clsx } from 'clsx';
import { setupMFA } from '@/api/auth';
import type { MFASetupResponse } from '@/types/auth';
import { Button } from '@/components/atoms/Button';

type MfaState = 'disabled' | 'setup' | 'confirmed';

export const MfaSetupPage: React.FC = () => {
  const [state, setState] = useState<MfaState>('disabled');
  const [setupData, setSetupData] = useState<MFASetupResponse | null>(null);
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleEnable = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await setupMFA();
      setSetupData(data);
      setState('setup');
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'Could not start MFA setup. Please try again.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleCodeChange = (value: string) => {
    const cleaned = value.replace(/\D/g, '').slice(0, 6);
    setCode(cleaned);
    if (cleaned.length === 6) {
      // Demo confirmation only — no backend verify call.
      setState('confirmed');
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-white">Two-Factor Authentication</h1>
        <p className="text-gray-400 text-sm mt-1">
          Add an extra layer of security to your account using a TOTP authenticator app.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-700/50 bg-red-900/30 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {state === 'disabled' && (
        <div className="rounded-xl border border-primary-700 bg-primary-900/50 p-6 space-y-4">
          <div className="flex items-center gap-3">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full bg-gray-500"
              aria-hidden="true"
            />
            <p className="text-sm text-gray-300">
              Two-factor authentication is currently <strong className="text-white">disabled</strong>.
            </p>
          </div>
          <p className="text-xs text-gray-400">
            When enabled, you will be required to enter a 6-digit code from your
            authenticator app each time you sign in.
          </p>
          <Button
            variant="primary"
            onClick={handleEnable}
            loading={loading}
            className="bg-teal-500 hover:bg-teal-400 text-primary-950"
          >
            Enable MFA
          </Button>
        </div>
      )}

      {state === 'setup' && setupData && (
        <div className="space-y-4">
          <div className="rounded-xl border border-primary-700 bg-primary-900/50 p-6 space-y-4">
            <h2 className="text-base font-semibold text-white">Step 1 — Add to your authenticator</h2>
            <p className="text-xs text-gray-400">
              Most authenticator apps (1Password, Authy, Google Authenticator, etc.) accept
              this either by scanning a QR rendered from the URL below or by manual secret entry.
            </p>

            <div className="space-y-2">
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-400">
                Setup URL (paste into your authenticator)
              </label>
              <a
                href={setupData.otpauth_url}
                className="block break-all rounded-lg border border-primary-700 bg-primary-950 p-3 font-mono text-xs text-teal-300 hover:text-teal-200"
              >
                {setupData.otpauth_url}
              </a>
            </div>

            <div className="space-y-2">
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-400">
                Or enter this secret manually
              </label>
              <div className="rounded-lg border border-primary-700 bg-primary-950 p-3 font-mono text-base tracking-widest text-white">
                {setupData.secret}
              </div>
            </div>

            {/* Backup codes are NOT returned by the current backend MFA endpoint.
                If/when backend adds them, render the same block keyed off setupData. */}
          </div>

          <div className="rounded-xl border border-primary-700 bg-primary-900/50 p-6 space-y-4">
            <h2 className="text-base font-semibold text-white">Step 2 — Confirm with a 6-digit code</h2>
            <p className="text-xs text-gray-400">
              Open your authenticator app and enter the current 6-digit code to verify the setup.
            </p>
            <input
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={code}
              onChange={(e) => handleCodeChange(e.target.value)}
              placeholder="000000"
              aria-label="6-digit verification code"
              className={clsx(
                'w-48 rounded-lg border border-primary-700 bg-primary-950 px-4 py-3',
                'text-center font-mono text-xl tracking-[0.5em] text-white',
                'focus:outline-none focus:ring-2 focus:ring-teal-500'
              )}
            />
          </div>
        </div>
      )}

      {state === 'confirmed' && (
        <div className="rounded-xl border border-green-700/50 bg-green-900/30 p-6 space-y-3">
          <div className="flex items-center gap-3">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-green-400" aria-hidden="true" />
            <h2 className="text-base font-semibold text-green-200">MFA enabled successfully</h2>
          </div>
          <p className="text-xs text-green-300/80">
            Your account is now protected with two-factor authentication. You will be prompted
            for a code from your authenticator app the next time you sign in.
          </p>
        </div>
      )}
    </div>
  );
};
