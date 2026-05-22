/**
 * ProtectedRoute layout component for ClinNote AI
 *
 * Redirects unauthenticated users to /login.
 * Enforces role-based access control.
 *
 * @example
 * <ProtectedRoute requiredRole="admin">
 *   <AdminPage />
 * </ProtectedRoute>
 */

import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import type { Role } from '@/types/auth';

export interface ProtectedRouteProps {
  children: React.ReactNode;
  /** Required role — if not provided, just checks authentication */
  requiredRole?: Role;
}

/**
 * Authentication and Role Guard
 */
export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  requiredRole,
}) => {
  const { isAuthenticated, user } = useAuthStore();
  const location = useLocation();

  // Not authenticated — redirect to login
  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        state={{ from: location.pathname }}
        replace
      />
    );
  }

  // Role check
  if (requiredRole && user?.role !== requiredRole) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4 p-6 text-center">
        <svg className="h-12 w-12 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <h2 className="text-xl font-semibold text-white">Access Denied</h2>
        <p className="text-gray-400 max-w-sm">
          You do not have permission to access this page.
          This area requires the <strong className="text-gray-200">{requiredRole}</strong> role.
        </p>
        <button
          onClick={() => window.history.back()}
          className="mt-2 px-4 py-2 rounded-lg bg-primary-700 text-gray-200 hover:bg-primary-600 transition-colors min-h-[44px]"
        >
          Go Back
        </button>
      </div>
    );
  }

  return <>{children}</>;
};
