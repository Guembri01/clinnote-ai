/**
 * CommandPalette organism for ClinNote AI
 *
 * Cmd+K / Ctrl+K spotlight-style command runner with fuzzy match,
 * keyboard navigation, and contextual visibility (admin-only entries).
 *
 * Mount the host once in the AppShell.
 *
 * Usage:
 *   <CommandPaletteHost />
 *
 *   // Open from anywhere:
 *   useCommandPalette().open()
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { create } from 'zustand';
import { useNavigate } from 'react-router-dom';
import { clsx } from 'clsx';
import { useAuthStore } from '@/store/authStore';
import { useThemeStore } from '@/store/themeStore';
import { useAuth } from '@/hooks/useAuth';
import { useEscapeKey } from '@/hooks/useEscapeKey';

interface PaletteStore {
  isOpen: boolean;
  open: () => void;
  close: () => void;
  toggle: () => void;
}

const usePaletteStore = create<PaletteStore>((set, get) => ({
  isOpen: false,
  open: () => set({ isOpen: true }),
  close: () => set({ isOpen: false }),
  toggle: () => set({ isOpen: !get().isOpen }),
}));

export function useCommandPalette() {
  const { open, close, toggle, isOpen } = usePaletteStore();
  return { open, close, toggle, isOpen };
}

interface Command {
  id: string;
  label: string;
  hint?: string;
  /** Optional category for grouping */
  group?: string;
  /** Optional admin guard */
  adminOnly?: boolean;
  /** Action handler */
  run: () => void;
  /** Render-time icon */
  icon: React.ReactNode;
  /** Keywords boosted in fuzzy match */
  keywords?: string[];
}

// Lightweight fuzzy match: case-insensitive substring + token order bonus.
function fuzzyScore(query: string, target: string): number {
  if (!query) return 1;
  const q = query.toLowerCase();
  const t = target.toLowerCase();
  if (t.includes(q)) return 100 - (t.indexOf(q) / Math.max(1, t.length)) * 50;
  // subsequence match
  let qi = 0;
  let lastIdx = -1;
  let bonus = 0;
  for (let i = 0; i < t.length && qi < q.length; i++) {
    if (t[i] === q[qi]) {
      if (lastIdx >= 0) bonus += 5 - Math.min(5, i - lastIdx);
      lastIdx = i;
      qi++;
    }
  }
  if (qi !== q.length) return 0;
  return 20 + bonus;
}

export const CommandPaletteHost: React.FC = () => {
  const { isOpen, close, toggle } = usePaletteStore();
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { logout } = useAuth();
  const toggleTheme = useThemeStore((s) => s.toggleTheme);
  const theme = useThemeStore((s) => s.theme);
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState('');
  const [selectedIdx, setSelectedIdx] = useState(0);

  // Global hotkey
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        toggle();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [toggle]);

  useEscapeKey(close, isOpen);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIdx(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [isOpen]);

  const commands: Command[] = useMemo(() => {
    const navIcon = (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
      </svg>
    );
    const cmds: Command[] = [
      {
        id: 'nav-new',
        label: 'New Session',
        group: 'Navigation',
        keywords: ['recording', 'start', 'create'],
        hint: 'Go to /sessions/new',
        icon: (
          <svg className="h-4 w-4 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
          </svg>
        ),
        run: () => {
          navigate('/sessions/new');
          close();
        },
      },
      {
        id: 'nav-dashboard',
        label: 'Dashboard',
        group: 'Navigation',
        keywords: ['home', 'overview'],
        hint: 'Go to /dashboard',
        icon: navIcon,
        run: () => {
          navigate('/dashboard');
          close();
        },
      },
      {
        id: 'nav-history',
        label: 'Notes History',
        group: 'Navigation',
        keywords: ['notes', 'past', 'records'],
        hint: 'Go to /notes',
        icon: navIcon,
        run: () => {
          navigate('/notes');
          close();
        },
      },
      {
        id: 'nav-my-sessions',
        label: 'View My Sessions',
        group: 'Navigation',
        keywords: ['mine', 'physician'],
        hint: 'Filter notes by current physician',
        icon: navIcon,
        run: () => {
          navigate('/notes?mine=1');
          close();
        },
      },
      {
        id: 'nav-admin',
        label: 'Admin Panel',
        group: 'Navigation',
        adminOnly: true,
        keywords: ['settings', 'manage', 'audit'],
        hint: 'Go to /admin',
        icon: (
          <svg className="h-4 w-4 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
        ),
        run: () => {
          navigate('/admin');
          close();
        },
      },
      {
        id: 'theme-toggle',
        label: theme === 'dark' ? 'Toggle Theme (→ light)' : 'Toggle Theme (→ dark)',
        group: 'Preferences',
        keywords: ['light', 'dark', 'mode', 'appearance'],
        icon: (
          <svg className="h-4 w-4 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
          </svg>
        ),
        run: () => {
          toggleTheme();
          close();
        },
      },
      {
        id: 'auth-signout',
        label: 'Sign Out',
        group: 'Account',
        keywords: ['logout', 'exit', 'leave'],
        icon: (
          <svg className="h-4 w-4 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
        ),
        run: () => {
          close();
          logout();
        },
      },
    ];

    return cmds.filter((c) => !c.adminOnly || user?.role === 'admin');
  }, [navigate, close, logout, theme, toggleTheme, user]);

  const filtered = useMemo(() => {
    if (!query.trim()) return commands;
    const scored = commands
      .map((c) => {
        const haystack = [c.label, c.hint ?? '', (c.keywords ?? []).join(' '), c.group ?? ''].join(' ');
        return { c, score: fuzzyScore(query, haystack) };
      })
      .filter((s) => s.score > 0)
      .sort((a, b) => b.score - a.score);
    return scored.map((s) => s.c);
  }, [commands, query]);

  // Clamp selection when filter shrinks
  useEffect(() => {
    if (selectedIdx >= filtered.length) setSelectedIdx(0);
  }, [filtered.length, selectedIdx]);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIdx((i) => Math.min(filtered.length - 1, i + 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIdx((i) => Math.max(0, i - 1));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const cmd = filtered[selectedIdx];
        if (cmd) cmd.run();
      }
    },
    [filtered, selectedIdx]
  );

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
      className="fixed inset-0 z-[70] flex items-start justify-center p-4 pt-24"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-md animate-fade-in"
        onClick={close}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        className={clsx(
          'relative w-full max-w-xl rounded-2xl overflow-hidden',
          'bg-primary-900/95 border border-teal-700/30 shadow-2xl',
          'animate-slide-in-up'
        )}
        style={{
          boxShadow:
            '0 24px 60px -16px rgba(0,0,0,.7), 0 0 0 1px rgba(45,212,191,.08), 0 0 32px rgba(45,212,191,.12)',
        }}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-primary-700">
          <svg className="h-5 w-5 text-teal-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIdx(0);
            }}
            onKeyDown={onKeyDown}
            placeholder="Type a command or search..."
            aria-label="Command palette search"
            className={clsx(
              'flex-1 bg-transparent text-base text-gray-100 placeholder-gray-500',
              'outline-none border-none focus:ring-0',
              'min-h-[40px]'
            )}
          />
          <kbd className="hidden tablet:inline-flex items-center gap-1 px-2 h-6 rounded border border-primary-700 bg-primary-800 text-[10px] text-gray-400 font-mono">
            ESC
          </kbd>
        </div>

        {/* Results */}
        <ul
          role="listbox"
          aria-label="Command results"
          className="max-h-80 overflow-y-auto py-2"
        >
          {filtered.length === 0 && (
            <li className="px-4 py-6 text-center text-sm text-gray-500">
              No commands match "{query}"
            </li>
          )}
          {filtered.map((cmd, idx) => {
            const selected = idx === selectedIdx;
            return (
              <li key={cmd.id} role="option" aria-selected={selected}>
                <button
                  type="button"
                  onMouseEnter={() => setSelectedIdx(idx)}
                  onClick={() => cmd.run()}
                  className={clsx(
                    'w-full flex items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors',
                    selected
                      ? 'bg-teal-900/30 text-white'
                      : 'text-gray-300 hover:bg-primary-800'
                  )}
                >
                  <span className="shrink-0">{cmd.icon}</span>
                  <span className="flex-1 min-w-0">
                    <span className="block font-medium truncate">{cmd.label}</span>
                    {cmd.hint && (
                      <span className="block text-xs text-gray-500 truncate">{cmd.hint}</span>
                    )}
                  </span>
                  {cmd.group && (
                    <span className="text-[10px] uppercase tracking-wider text-gray-500">
                      {cmd.group}
                    </span>
                  )}
                  {selected && (
                    <kbd className="hidden tablet:inline-flex items-center gap-1 px-1.5 h-5 rounded border border-primary-700 bg-primary-800 text-[10px] text-teal-300 font-mono">
                      ↵
                    </kbd>
                  )}
                </button>
              </li>
            );
          })}
        </ul>

        {/* Footer hint strip */}
        <div className="flex items-center justify-between px-4 py-2 border-t border-primary-700 bg-primary-950/50 text-[10px] text-gray-500">
          <span className="flex items-center gap-3">
            <span>
              <kbd className="font-mono text-gray-400">↑↓</kbd> navigate
            </span>
            <span>
              <kbd className="font-mono text-gray-400">↵</kbd> select
            </span>
            <span>
              <kbd className="font-mono text-gray-400">esc</kbd> close
            </span>
          </span>
          <span className="font-semibold tracking-wider text-teal-400">⌘K</span>
        </div>
      </div>
    </div>
  );
};
