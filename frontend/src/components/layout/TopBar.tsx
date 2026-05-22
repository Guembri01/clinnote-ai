/**
 * TopBar layout component for ClinNote AI
 *
 * User avatar, session status indicator, theme toggle, notifications,
 * and command palette opener.
 */

import React from 'react';
import { clsx } from 'clsx';
import { useAuth } from '@/hooks/useAuth';
import { useRecordingStore } from '@/store/recordingStore';
import { useThemeStore } from '@/store/themeStore';
import { useCommandPalette } from '@/components/organisms/CommandPalette';
import { Avatar } from '@/components/atoms/Avatar';

export interface TopBarProps {
  /** Page title to display */
  title?: string;
  /** Open sidebar callback (mobile) */
  onOpenSidebar?: () => void;
}

/**
 * Top Application Bar
 */
export const TopBar: React.FC<TopBarProps> = ({ title, onOpenSidebar }) => {
  const { user, logout } = useAuth();
  const { status } = useRecordingStore();
  const [dropdownOpen, setDropdownOpen] = React.useState(false);
  const { open: openPalette } = useCommandPalette();
  const theme = useThemeStore((s) => s.theme);
  const toggleTheme = useThemeStore((s) => s.toggleTheme);

  const isRecording = status === 'recording';
  const isPaused = status === 'paused';
  const unreadNotifications = 2; // mock: true

  return (
    <header
      className="flex items-center justify-between gap-3 px-4 py-3 bg-primary-900 border-b border-primary-800 h-16"
      role="banner"
    >
      {/* Left: menu + title */}
      <div className="flex items-center gap-3">
        {/* Mobile menu button */}
        {onOpenSidebar && (
          <button
            onClick={onOpenSidebar}
            aria-label="Open navigation menu"
            className="tablet:hidden p-2 rounded-lg text-gray-400 hover:text-white hover:bg-primary-800 min-h-[44px] min-w-[44px] flex items-center justify-center"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        )}

        {title && (
          <h1 className="text-base font-semibold text-gray-100 hidden tablet:block">{title}</h1>
        )}
      </div>

      {/* Center: recording status indicator OR command palette button */}
      <div className="flex-1 flex items-center justify-center">
        {isRecording || isPaused ? (
          <div
            aria-live="polite"
            className={clsx(
              'flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium',
              isRecording
                ? 'bg-red-900/40 border border-red-700 text-red-300'
                : 'bg-amber-900/40 border border-amber-700 text-amber-300'
            )}
          >
            <span
              className={clsx(
                'h-2 w-2 rounded-full',
                isRecording ? 'bg-red-400 animate-pulse' : 'bg-amber-400'
              )}
              aria-hidden="true"
            />
            {isRecording ? 'Recording in progress' : 'Recording paused'}
          </div>
        ) : (
          <button
            type="button"
            onClick={openPalette}
            aria-label="Open command palette (Ctrl K)"
            className={clsx(
              'hidden tablet:inline-flex items-center gap-2',
              'px-3 py-1.5 rounded-lg min-h-[36px]',
              'bg-primary-800/60 border border-primary-700',
              'text-gray-400 hover:text-gray-200 hover:border-teal-700/60',
              'transition-colors text-xs'
            )}
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <span>Search commands</span>
            <kbd className="ml-2 px-1.5 h-5 inline-flex items-center rounded border border-primary-600 bg-primary-900 text-[10px] text-teal-300 font-mono">
              ⌘K
            </kbd>
          </button>
        )}
      </div>

      {/* Right: user controls */}
      <div className="flex items-center gap-2">
        {/* Theme toggle */}
        <button
          type="button"
          onClick={toggleTheme}
          aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          className="p-2 rounded-lg text-gray-400 hover:text-teal-300 hover:bg-primary-800 min-h-[44px] min-w-[44px] flex items-center justify-center transition-colors"
        >
          {theme === 'dark' ? (
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          ) : (
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
          )}
        </button>

        {/* Notifications bell */}
        <button
          type="button"
          aria-label={`Notifications (${unreadNotifications} unread)`}
          className="relative p-2 rounded-lg text-gray-400 hover:text-teal-300 hover:bg-primary-800 min-h-[44px] min-w-[44px] flex items-center justify-center transition-colors"
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
          {unreadNotifications > 0 && (
            <span
              className="absolute top-1.5 right-1.5 h-4 min-w-[16px] px-1 rounded-full bg-red-500 text-[10px] font-bold text-white flex items-center justify-center"
              aria-hidden="true"
            >
              {unreadNotifications}
            </span>
          )}
        </button>

        {/* User avatar + dropdown */}
        {user && (
          <div className="relative">
            <button
              onClick={() => setDropdownOpen(!dropdownOpen)}
              aria-label="User menu"
              aria-haspopup="true"
              aria-expanded={dropdownOpen}
              className={clsx(
                'flex items-center gap-2 rounded-lg px-2 py-1.5',
                'hover:bg-primary-800 transition-colors',
                'min-h-[44px] min-w-[44px]'
              )}
            >
              <Avatar name={user.full_name} src={user.avatar_url} size="sm" />
              <div className="hidden tablet:block text-left">
                <p className="text-sm font-medium text-gray-200 leading-tight">{user.full_name}</p>
                <p className="text-xs text-gray-500 capitalize">{user.role.replace('_', ' ')}</p>
              </div>
              <svg className="h-4 w-4 text-gray-400 hidden tablet:block" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {/* Dropdown menu */}
            {dropdownOpen && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setDropdownOpen(false)}
                  aria-hidden="true"
                />
                <div
                  className={clsx(
                    'absolute right-0 top-full mt-1 z-20',
                    'w-52 rounded-xl bg-primary-800 border border-primary-600 shadow-xl',
                    'py-1 animate-fade-in'
                  )}
                  role="menu"
                >
                  <div className="px-4 py-3 border-b border-primary-700">
                    <p className="text-sm font-medium text-gray-200">{user.full_name}</p>
                    <p className="text-xs text-gray-400">{user.email}</p>
                  </div>

                  {user.facility && (
                    <div className="px-4 py-2">
                      <p className="text-xs text-gray-500">{user.facility}</p>
                    </div>
                  )}

                  <div className="border-t border-primary-700 mt-1 pt-1">
                    <button
                      role="menuitem"
                      onClick={() => { logout(); setDropdownOpen(false); }}
                      className={clsx(
                        'w-full flex items-center gap-2 px-4 py-2.5 text-sm text-gray-400',
                        'hover:bg-primary-700 hover:text-white transition-colors min-h-[44px] text-left'
                      )}
                    >
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                      </svg>
                      Sign Out
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </header>
  );
};
