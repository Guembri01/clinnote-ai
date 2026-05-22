/**
 * Toast notification system for ClinNote AI
 *
 * Lightweight self-contained toast without external dependencies.
 * Provides a Toaster component and a useToast hook.
 *
 * @example
 * // In App.tsx:  <Toaster />
 * // In component: const { toast } = useToast(); toast.success("Note approved!");
 */

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { clsx } from 'clsx';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface ToastItem {
  id: string;
  type: ToastType;
  message: string;
  duration?: number;
}

interface ToastContextValue {
  toasts: ToastItem[];
  addToast: (type: ToastType, message: string, duration?: number) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

/** Toast provider — wrap your app with this */
export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback((type: ToastType, message: string, duration = 4000) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    setToasts((prev) => [...prev.slice(-4), { id, type, message, duration }]);
    if (duration > 0) {
      setTimeout(() => removeToast(id), duration);
    }
  }, [removeToast]);

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
    </ToastContext.Provider>
  );
};

/** Hook to trigger toasts */
export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');

  const toast = {
    success: (message: string, duration?: number) => ctx.addToast('success', message, duration),
    error: (message: string, duration?: number) => ctx.addToast('error', message, duration),
    warning: (message: string, duration?: number) => ctx.addToast('warning', message, duration),
    info: (message: string, duration?: number) => ctx.addToast('info', message, duration),
  };
  return { toast, removeToast: ctx.removeToast };
}

const typeConfig: Record<ToastType, { icon: React.ReactNode; classes: string }> = {
  success: {
    icon: (
      <svg className="h-5 w-5 text-green-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
      </svg>
    ),
    classes: 'bg-green-950 border-green-700 text-green-200',
  },
  error: {
    icon: (
      <svg className="h-5 w-5 text-red-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    classes: 'bg-red-950 border-red-700 text-red-200',
  },
  warning: {
    icon: (
      <svg className="h-5 w-5 text-amber-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
    ),
    classes: 'bg-amber-950 border-amber-700 text-amber-200',
  },
  info: {
    icon: (
      <svg className="h-5 w-5 text-teal-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    classes: 'bg-teal-950 border-teal-700 text-teal-200',
  },
};

/** Individual toast item */
const ToastCard: React.FC<{ toast: ToastItem; onDismiss: (id: string) => void }> = ({
  toast,
  onDismiss,
}) => {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Trigger enter animation
    const t = setTimeout(() => setVisible(true), 10);
    return () => clearTimeout(t);
  }, []);

  const config = typeConfig[toast.type];

  return (
    <div
      role="alert"
      aria-live="polite"
      className={clsx(
        'flex items-start gap-3 px-4 py-3 rounded-xl border shadow-2xl max-w-sm w-full',
        'transition-all duration-300',
        config.classes,
        visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'
      )}
    >
      {config.icon}
      <p className="text-sm font-medium flex-1 leading-snug">{toast.message}</p>
      <button
        onClick={() => onDismiss(toast.id)}
        aria-label="Dismiss notification"
        className="ml-auto p-0.5 opacity-60 hover:opacity-100 transition-opacity shrink-0"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
};

/** Renders toasts — place once inside ToastProvider */
export const Toaster: React.FC = () => {
  const ctx = useContext(ToastContext);
  if (!ctx || ctx.toasts.length === 0) return null;

  return (
    <div
      aria-label="Notifications"
      className="fixed bottom-5 right-5 z-[9999] flex flex-col gap-2 pointer-events-none"
    >
      {ctx.toasts.map((t) => (
        <div key={t.id} className="pointer-events-auto">
          <ToastCard toast={t} onDismiss={ctx.removeToast} />
        </div>
      ))}
    </div>
  );
};
