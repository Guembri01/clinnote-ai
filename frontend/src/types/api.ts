/**
 * API utility types for ClinNote AI
 */

/** Standard API error shape */
export interface APIError {
  status: number;
  code: string;
  message: string;
  details?: Record<string, string[]>;
  timestamp: string;
}

/** Standard API response wrapper */
export interface APIResponse<T> {
  data: T;
  message?: string;
  timestamp: string;
}

/** Paginated API response */
export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

/** Query parameters for paginated requests */
export interface PaginationParams {
  page?: number;
  page_size?: number;
  search?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

/** Date range filter */
export interface DateRangeFilter {
  start_date?: string;
  end_date?: string;
}

/** Usage statistics for admin dashboard */
export interface UsageStats {
  total_sessions: number;
  total_notes: number;
  approved_notes: number;
  pending_approval: number;
  avg_session_duration_seconds: number;
  sessions_today: number;
  notes_generated_today: number;
  active_physicians: number;
}

/** Active session for admin monitoring */
export interface ActiveSession {
  session_id: string;
  physician_name: string;
  physician_id: string;
  patient_mrn: string;
  status: string;
  duration_seconds: number;
  started_at: string;
}

/** Audit log entry */
export interface AuditLogEntry {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  user_id: string;
  user_name: string;
  user_role: string;
  ip_address: string;
  timestamp: string;
  details?: Record<string, unknown>;
  patient_mrn?: string;
}
