/**
 * Authentication hook for ClinNote AI
 *
 * Provides login, logout, MFA verification, and current user state.
 *
 * @example
 * const { user, isAuthenticated, login, logout } = useAuth();
 */

import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import * as authAPI from '@/api/auth';
import { tokenStorage } from '@/api/client';
import type { LoginCredentials, User } from '@/types/auth';
import type { APIError } from '@/types/api';

export interface UseAuthReturn {
  /** Current authenticated user */
  user: User | null;
  /** Whether the user is authenticated */
  isAuthenticated: boolean;
  /** Whether MFA verification is required */
  mfaRequired: boolean;
  /** Temporary token for MFA flow */
  tempToken: string | null;
  /**
   * Login with email and password
   * @throws APIError on failure
   */
  login: (credentials: LoginCredentials) => Promise<void>;
  /**
   * Complete MFA verification with TOTP code
   * @throws APIError on failure
   */
  verifyMFA: (code: string) => Promise<void>;
  /** Logout and clear all auth state */
  logout: () => Promise<void>;
  /** Current user role */
  role: string | null;
  /** Whether the current user is an admin */
  isAdmin: boolean;
}

export function useAuth(): UseAuthReturn {
  const navigate = useNavigate();
  const {
    user,
    isAuthenticated,
    mfaRequired,
    tempToken,
    setAuth,
    setTempToken,
    clearAuth,
  } = useAuthStore();

  const login = useCallback(
    async (credentials: LoginCredentials): Promise<void> => {
      const response = await authAPI.login(credentials);

      if (response.requires_mfa && response.access_token) {
        // Store the mfa_pending token; LoginPage renders the TOTP prompt
        setTempToken(response.access_token, true);
        return;
      }

      // Backend's TokenResponse doesn't include the user — fetch /users/me to hydrate it
      const me = await authAPI.getMe();
      setAuth(me, response.access_token);
      navigate('/dashboard', { replace: true });
    },
    [setAuth, setTempToken, navigate]
  );

  const verifyMFA = useCallback(
    async (code: string): Promise<void> => {
      if (!tempToken) {
        throw { status: 400, code: 'NO_TEMP_TOKEN', message: 'No temporary token found', timestamp: new Date().toISOString() } as APIError;
      }

      const response = await authAPI.verifyMFA({ totp_code: code, token: tempToken });
      const me = await authAPI.getMe();
      setAuth(me, response.access_token);
      navigate('/dashboard', { replace: true });
    },
    [tempToken, setAuth, navigate]
  );

  const logout = useCallback(async (): Promise<void> => {
    try {
      await authAPI.logout();
    } finally {
      clearAuth();
      tokenStorage.clearTokens();
      navigate('/login', { replace: true });
    }
  }, [clearAuth, navigate]);

  return {
    user,
    isAuthenticated,
    mfaRequired,
    tempToken,
    login,
    verifyMFA,
    logout,
    role: user?.role ?? null,
    isAdmin: user?.role === 'admin',
  };
}
