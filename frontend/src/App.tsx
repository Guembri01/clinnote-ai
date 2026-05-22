/**
 * Root App component for ClinNote AI
 *
 * Provides:
 * - QueryClient (TanStack Query)
 * - React Router
 * - Global error boundary
 * - Global query-invalidation event bus (cn:invalidate)
 * - Theme class sync from Zustand → <html>
 */

import React from 'react';
import { RouterProvider } from 'react-router-dom';
import { QueryClient, QueryClientProvider, type QueryKey } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { router } from './router';
import { ToastProvider, Toaster } from '@/components/atoms/Toast';
import { useThemeStore } from '@/store/themeStore';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      retry: (failureCount, error) => {
        // Don't retry on 4xx errors (client errors)
        if (error && typeof error === 'object' && 'status' in error) {
          const status = (error as { status: number }).status;
          if (status >= 400 && status < 500) return false;
        }
        return failureCount < 2;
      },
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: false,
    },
  },
});

// Listen for auth:logout events from the API client
window.addEventListener('auth:logout', () => {
  queryClient.clear();
});

// Global cross-component invalidation bus.
// Any component can call:
//   window.dispatchEvent(new CustomEvent('cn:invalidate', { detail: ['notes-history'] }))
// to refetch a query without prop drilling.
window.addEventListener('cn:invalidate', (e: Event) => {
  const ce = e as CustomEvent<QueryKey>;
  if (ce.detail) {
    queryClient.invalidateQueries({ queryKey: ce.detail });
  }
});

/**
 * Root Application
 */
const App: React.FC = () => {
  const theme = useThemeStore((s) => s.theme);
  const isScreenshotMode =
    typeof window !== 'undefined' &&
    (new URLSearchParams(window.location.search).has('screenshot') ||
      (window as unknown as { __CLINNOTE_SCREENSHOT_MODE?: boolean })
        .__CLINNOTE_SCREENSHOT_MODE === true);

  // Sync theme class on <html> for Tailwind's class-based darkMode + .theme-light override
  React.useEffect(() => {
    const root = document.documentElement;
    root.classList.remove('theme-light', 'theme-dark', 'dark');
    if (theme === 'light') {
      root.classList.add('theme-light');
    } else {
      root.classList.add('dark', 'theme-dark');
    }
  }, [theme]);

  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <ErrorBoundary>
          <RouterProvider router={router} />
        </ErrorBoundary>
        <Toaster />
        {import.meta.env.DEV && !isScreenshotMode && <ReactQueryDevtools initialIsOpen={false} />}
      </ToastProvider>
    </QueryClientProvider>
  );
};

/** Global error boundary */
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[ClinNote AI] Uncaught error:', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-gray-950 flex items-center justify-center p-6">
          <div className="max-w-md w-full text-center space-y-4">
            <div className="flex justify-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-red-900/40">
                <svg className="h-8 w-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            </div>
            <h1 className="text-xl font-bold text-white">Something went wrong</h1>
            <p className="text-gray-400 text-sm">
              An unexpected error occurred. Please refresh the page.
            </p>
            {this.state.error && (
              <details className="text-left rounded-lg bg-gray-900 p-3 border border-gray-700">
                <summary className="text-xs text-gray-500 cursor-pointer">Error details</summary>
                <pre className="text-xs text-red-400 mt-2 overflow-auto">
                  {this.state.error.message}
                </pre>
              </details>
            )}
            <button
              onClick={() => window.location.reload()}
              className="px-6 py-3 rounded-lg bg-primary-700 text-white hover:bg-primary-600 transition-colors min-h-[44px]"
            >
              Refresh Page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default App;
