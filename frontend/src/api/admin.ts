/**
 * Admin API functions for ClinNote AI
 */

import apiClient from './client';
import type { ActiveSession, AuditLogEntry, UsageStats } from '@/types/api';
import type { PaginatedResponse, PaginationParams, DateRangeFilter } from '@/types/api';

/** Admin-scope user record returned by GET /users (mirrors backend UserRead schema) */
export interface AdminUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  specialty: string | null;
  npi_number: string | null;
  org_id: string | null;
  ehr_system: string | null;
  is_active: boolean;
  totp_enabled: boolean;
  created_at: string;
  updated_at: string;
}

/**
 * List all users (admin scope)
 */
export async function listUsers(): Promise<AdminUser[]> {
  const { data } = await apiClient.get<AdminUser[]>('/users');
  return data;
}

/**
 * Get all currently active recording sessions
 */
export async function getActiveSessions(): Promise<ActiveSession[]> {
  const { data } = await apiClient.get<ActiveSession[]>('/admin/sessions/active');
  return data;
}

/**
 * Get system usage statistics
 */
export async function getUsageStats(dateRange?: DateRangeFilter): Promise<UsageStats> {
  const { data } = await apiClient.get<UsageStats>('/admin/stats', { params: dateRange });
  return data;
}

/**
 * Get paginated HIPAA audit log
 */
export async function getAuditLog(
  params?: PaginationParams &
    DateRangeFilter & {
      user_id?: string;
      action?: string;
      resource_type?: string;
    }
): Promise<PaginatedResponse<AuditLogEntry>> {
  const { data } = await apiClient.get<PaginatedResponse<AuditLogEntry>>('/admin/audit-log', {
    params,
  });
  return data;
}

/**
 * Terminate an active session (emergency stop)
 */
export async function terminateSession(sessionId: string, reason: string): Promise<void> {
  await apiClient.post(`/admin/sessions/${sessionId}/terminate`, { reason });
}
