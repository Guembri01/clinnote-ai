/**
 * Application router for ClinNote AI
 *
 * Protected routes, role guards, and nested layouts.
 * Route-level code splitting via React.lazy() — keeps initial bundle small.
 */

import React, { lazy, Suspense } from 'react';
import {
  createBrowserRouter,
  Navigate,
} from 'react-router-dom';
import { AppShell } from '@/components/layout/AppShell';
import { ProtectedRoute } from '@/components/layout/ProtectedRoute';
// LoginPage is eager — first paint, lowest TTI
import { LoginPage } from '@/pages/LoginPage';

// Lazy routes — split into separate chunks
const ForgotPasswordPage = lazy(() => import('@/pages/ForgotPasswordPage').then(m => ({ default: m.ForgotPasswordPage })));
const DashboardPage = lazy(() => import('@/pages/DashboardPage').then(m => ({ default: m.DashboardPage })));
const NewSessionPage = lazy(() => import('@/pages/NewSessionPage').then(m => ({ default: m.NewSessionPage })));
const ReviewNotePage = lazy(() => import('@/pages/ReviewNotePage').then(m => ({ default: m.ReviewNotePage })));
const NotesHistoryPage = lazy(() => import('@/pages/NotesHistoryPage').then(m => ({ default: m.NotesHistoryPage })));
const AdminPage = lazy(() => import('@/pages/AdminPage').then(m => ({ default: m.AdminPage })));
const MfaSetupPage = lazy(() => import('@/pages/MfaSetupPage').then(m => ({ default: m.MfaSetupPage })));

/**
 * Route fallback shown during lazy chunk load.
 * Centered teal spinner with subtle fade.
 */
const RouteFallback: React.FC = () => (
  <div
    role="status"
    aria-live="polite"
    className="flex flex-col items-center justify-center gap-3 py-20 animate-fade-in"
  >
    <span className="relative inline-flex h-10 w-10">
      <span className="absolute inset-0 rounded-full border-2 border-teal-500/20" aria-hidden="true" />
      <span
        className="absolute inset-0 rounded-full border-2 border-transparent border-t-teal-400 animate-spin"
        aria-hidden="true"
      />
    </span>
    <p className="text-xs text-gray-500 tracking-wider uppercase">Loading module</p>
  </div>
);

/** Wrap a lazy element in Suspense */
const lazyRoute = (Element: React.ComponentType): React.ReactElement => (
  <Suspense fallback={<RouteFallback />}>
    <Element />
  </Suspense>
);

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/forgot-password',
    element: lazyRoute(ForgotPasswordPage),
  },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <AppShell />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <Navigate to="/dashboard" replace />,
      },
      {
        path: 'dashboard',
        element: lazyRoute(DashboardPage),
      },
      {
        path: 'sessions/new',
        element: lazyRoute(NewSessionPage),
      },
      {
        path: 'notes',
        element: lazyRoute(NotesHistoryPage),
      },
      {
        path: 'notes/:id/review',
        element: lazyRoute(ReviewNotePage),
      },
      {
        path: 'admin',
        element: (
          <ProtectedRoute requiredRole="admin">
            {lazyRoute(AdminPage)}
          </ProtectedRoute>
        ),
      },
      {
        path: 'settings/mfa',
        element: lazyRoute(MfaSetupPage),
      },
      {
        path: '*',
        element: (
          <div className="flex flex-col items-center justify-center py-20 text-center gap-4">
            <svg className="h-16 w-16 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <h2 className="text-xl font-semibold text-white">Page Not Found</h2>
              <p className="text-gray-400 text-sm mt-1">The page you're looking for doesn't exist</p>
            </div>
            <a
              href="/dashboard"
              className="px-4 py-2 rounded-lg bg-primary-700 text-gray-200 hover:bg-primary-600 transition-colors min-h-[44px] flex items-center"
            >
              Go to Dashboard
            </a>
          </div>
        ),
      },
    ],
  },
]);
