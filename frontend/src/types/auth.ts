/**
 * Authentication and user management types for ClinNote AI
 */

/** User roles within the system */
export type Role = 'physician' | 'nurse' | 'admin' | 'medical_assistant';

/** Authenticated user profile */
export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  department?: string;
  facility?: string;
  npi?: string; // National Provider Identifier
  avatar_url?: string;
  mfa_enabled: boolean;
  created_at: string;
  last_login?: string;
}

/** Login credentials submitted by the user */
export interface LoginCredentials {
  email: string;
  password: string;
}

/** Token response from the backend /auth/login + /auth/verify-mfa endpoints */
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  expires_in: number; // seconds
  /** Backend field name is `requires_mfa` (see TokenResponse Pydantic schema) */
  requires_mfa: boolean;
}

/** MFA verification payload — backend expects `token` (not `temp_token`) */
export interface MFAVerifyRequest {
  totp_code: string;
  token: string;
}

/** MFA setup response — backend `TOTPSetupResponse` returns these two fields */
export interface MFASetupResponse {
  /** OTPAuth URL to encode in a QR code or paste into an authenticator */
  otpauth_url: string;
  /** Base32 TOTP secret — show once, do not store client-side */
  secret: string;
}

/** Refresh token request */
export interface RefreshTokenRequest {
  refresh_token: string;
}
