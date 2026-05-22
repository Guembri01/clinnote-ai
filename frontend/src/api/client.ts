/**
 * Axios HTTP client for ClinNote AI
 *
 * Features:
 * - JWT Authorization header injection
 * - Automatic 401 → refresh token → retry
 * - 30 second request timeout
 * - Normalized error responses
 */

import axios, {
  type AxiosInstance,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
  type AxiosResponse,
  AxiosError,
} from 'axios';
import type { APIError } from '@/types/api';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8003/api/v1';
const REQUEST_TIMEOUT_MS = 30_000;

// Create the main Axios instance
const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: REQUEST_TIMEOUT_MS,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

// Token storage helpers — sessionStorage for HIPAA (clears on tab close)
export const tokenStorage = {
  getAccessToken: (): string | null => sessionStorage.getItem('clinnote_access_token'),
  setAccessToken: (token: string): void => sessionStorage.setItem('clinnote_access_token', token),
  getRefreshToken: (): string | null => sessionStorage.getItem('clinnote_refresh_token'),
  setRefreshToken: (token: string): void => sessionStorage.setItem('clinnote_refresh_token', token),
  clearTokens: (): void => {
    sessionStorage.removeItem('clinnote_access_token');
    sessionStorage.removeItem('clinnote_refresh_token');
  },
};

// Track in-progress refresh to prevent duplicate calls
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

const processQueue = (error: unknown, token: string | null = null): void => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else if (token) {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

// Request interceptor — inject JWT
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig): InternalAxiosRequestConfig => {
    const token = tokenStorage.getAccessToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: unknown) => Promise.reject(error)
);

// Response interceptor — handle 401 + refresh
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: unknown) => {
    if (!(error instanceof AxiosError) || !error.config) {
      return Promise.reject(normalizeError(error));
    }

    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };

    // Handle 401 — attempt token refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      const refreshToken = tokenStorage.getRefreshToken();

      if (!refreshToken) {
        // No refresh token — clear auth and redirect to login
        tokenStorage.clearTokens();
        window.dispatchEvent(new CustomEvent('auth:logout'));
        return Promise.reject(normalizeError(error));
      }

      if (isRefreshing) {
        // Queue this request until refresh completes
        return new Promise<string>((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${token}`;
            }
            return apiClient(originalRequest);
          })
          .catch((err: unknown) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const response = await axios.post(`${BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        });
        const { access_token, refresh_token: newRefreshToken } = response.data;

        tokenStorage.setAccessToken(access_token);
        if (newRefreshToken) tokenStorage.setRefreshToken(newRefreshToken);

        apiClient.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;

        processQueue(null, access_token);

        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
        }

        return apiClient(originalRequest);
      } catch (refreshError: unknown) {
        processQueue(refreshError, null);
        tokenStorage.clearTokens();
        window.dispatchEvent(new CustomEvent('auth:logout'));
        return Promise.reject(normalizeError(refreshError));
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(normalizeError(error));
  }
);

/** Normalize any error into a consistent APIError shape */
export function normalizeError(error: unknown): APIError {
  if (error instanceof AxiosError && error.response) {
    const data = error.response.data as Partial<APIError>;
    return {
      status: error.response.status,
      code: data.code ?? 'API_ERROR',
      message: data.message ?? error.message ?? 'An unexpected error occurred',
      details: data.details,
      timestamp: data.timestamp ?? new Date().toISOString(),
    };
  }

  if (error instanceof AxiosError && error.request) {
    return {
      status: 0,
      code: 'NETWORK_ERROR',
      message: 'Network error — please check your connection',
      timestamp: new Date().toISOString(),
    };
  }

  return {
    status: 0,
    code: 'UNKNOWN_ERROR',
    message: error instanceof Error ? error.message : 'An unknown error occurred',
    timestamp: new Date().toISOString(),
  };
}

export default apiClient;
