/**
 * Authentication API functions for ClinNote AI
 */

import apiClient, { tokenStorage } from './client';
import type {
  LoginCredentials,
  TokenResponse,
  MFAVerifyRequest,
  MFASetupResponse,
  RefreshTokenRequest,
  User,
} from '@/types/auth';

/**
 * Login with email and password.
 * Backend may set requires_mfa=true and return a short-lived mfa_pending token —
 * in that case the access/refresh tokens are NOT persisted; verifyMFA() finishes the flow.
 */
export async function login(credentials: LoginCredentials): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>('/auth/login', credentials);
  if (!data.requires_mfa) {
    tokenStorage.setAccessToken(data.access_token);
    tokenStorage.setRefreshToken(data.refresh_token);
  }
  return data;
}

/**
 * Complete MFA verification with TOTP code.
 * Backend path is /auth/verify-mfa (hyphenated, not /auth/mfa/verify).
 */
export async function verifyMFA(payload: MFAVerifyRequest): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>('/auth/verify-mfa', payload);
  tokenStorage.setAccessToken(data.access_token);
  tokenStorage.setRefreshToken(data.refresh_token);
  return data;
}

/**
 * Enable TOTP MFA — returns the otpauth URL and base32 secret (show once).
 */
export async function setupMFA(): Promise<MFASetupResponse> {
  const { data } = await apiClient.post<MFASetupResponse>('/auth/mfa/setup');
  return data;
}

/**
 * Fetch the authenticated user's own profile.
 * Backend's TokenResponse does not include the user object, so we hydrate it separately.
 */
export async function getMe(): Promise<User> {
  const { data } = await apiClient.get<{
    id: string;
    email: string;
    first_name: string;
    last_name: string;
    role: User['role'];
    specialty?: string;
    npi_number?: string;
    totp_enabled?: boolean;
    is_active?: boolean;
    created_at: string;
    last_login?: string;
  }>('/users/me');
  return {
    id: data.id,
    email: data.email,
    full_name: `${data.first_name} ${data.last_name}`.trim(),
    role: data.role,
    department: data.specialty,
    npi: data.npi_number,
    mfa_enabled: data.totp_enabled ?? false,
    created_at: data.created_at,
    last_login: data.last_login,
  };
}

/**
 * Refresh the access token using the stored refresh token
 */
export async function refreshToken(payload: RefreshTokenRequest): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>('/auth/refresh', payload);
  tokenStorage.setAccessToken(data.access_token);
  if (data.refresh_token) tokenStorage.setRefreshToken(data.refresh_token);
  return data;
}

/**
 * Logout — revokes tokens server-side and clears local storage
 */
export async function logout(): Promise<void> {
  const refreshTokenValue = tokenStorage.getRefreshToken();
  try {
    await apiClient.post('/auth/logout', { refresh_token: refreshTokenValue });
  } catch {
    // Best effort — always clear local tokens
  } finally {
    tokenStorage.clearTokens();
  }
}
