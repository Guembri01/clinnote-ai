/**
 * Authentication Zustand store for ClinNote AI
 *
 * Uses sessionStorage (not localStorage) for HIPAA compliance.
 * All PHI is cleared when the browser tab is closed.
 */

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { User } from '@/types/auth';

interface AuthState {
  /** Authenticated user profile */
  user: User | null;
  /** JWT access token */
  accessToken: string | null;
  /** Whether the user is currently authenticated */
  isAuthenticated: boolean;
  /** Temporary token from first MFA step */
  tempToken: string | null;
  /** Whether MFA verification is required */
  mfaRequired: boolean;
}

interface AuthActions {
  /** Set the authenticated user and token */
  setAuth: (user: User, token: string) => void;
  /** Set temporary token for MFA flow */
  setTempToken: (token: string, mfaRequired: boolean) => void;
  /** Clear all auth state — called on logout or session expiry */
  clearAuth: () => void;
  /** Update user profile */
  updateUser: (updates: Partial<User>) => void;
}

export type AuthStore = AuthState & AuthActions;

const initialState: AuthState = {
  user: null,
  accessToken: null,
  isAuthenticated: false,
  tempToken: null,
  mfaRequired: false,
};

export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      ...initialState,

      setAuth: (user: User, token: string) => {
        set({
          user,
          accessToken: token,
          isAuthenticated: true,
          tempToken: null,
          mfaRequired: false,
        });
      },

      setTempToken: (token: string, mfaRequired: boolean) => {
        set({ tempToken: token, mfaRequired, isAuthenticated: false });
      },

      clearAuth: () => {
        set(initialState);
      },

      updateUser: (updates: Partial<User>) => {
        set((state) => ({
          user: state.user ? { ...state.user, ...updates } : null,
        }));
      },
    }),
    {
      name: 'clinnote-auth',
      // HIPAA: Use sessionStorage — data cleared when tab closes
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
