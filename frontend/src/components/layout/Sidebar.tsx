/**
 * Sidebar layout component for ClinNote AI
 *
 * Navigation sidebar with role-based menu items, AI status pill,
 * and a role badge near the logout control.
 */

import React from 'react';
import { NavLink } from 'react-router-dom';
import { clsx } from 'clsx';
import { useAuthStore } from '@/store/authStore';
import { useAuth } from '@/hooks/useAuth';

interface NavItem {
  to: string;
  label: string;
  icon: React.ReactNode;
  adminOnly?: boolean;
  badge?: number;
}

const navItems: NavItem[] = [
  {
    to: '/dashboard',
    label: 'Dashboard',
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
      </svg>
    ),
  },
  {
    to: '/sessions/new',
    label: 'New Session',
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
      </svg>
    ),
  },
  {
    to: '/notes',
    label: 'History',
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
  },
  {
    to: '/admin',
    label: 'Admin',
    adminOnly: true,
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
  {
    to: '/settings/mfa',
    label: 'Settings',
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
];

export interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
}

const roleBadgeStyles: Record<string, string> = {
  admin: 'bg-amber-900/40 border-amber-700/50 text-amber-300',
  physician: 'bg-teal-900/40 border-teal-700/50 text-teal-300',
  nurse: 'bg-primary-700/60 border-primary-600 text-primary-200',
  default: 'bg-primary-700/60 border-primary-600 text-gray-300',
};

/**
 * Navigation Sidebar
 */
export const Sidebar: React.FC<SidebarProps> = ({ isOpen = true, onClose }) => {
  const { user } = useAuthStore();
  const { logout } = useAuth();
  const isAdmin = user?.role === 'admin';

  const visibleItems = navItems.filter((item) => !item.adminOnly || isAdmin);
  const roleClass = (user && roleBadgeStyles[user.role]) || roleBadgeStyles.default;

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && onClose && (
        <div
          className="fixed inset-0 z-20 bg-black/60 tablet:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <nav
        aria-label="Main navigation"
        className={clsx(
          'flex flex-col h-full w-64',
          'bg-primary-900 border-r border-primary-800',
          'transition-transform duration-300 ease-in-out',
          // Mobile: slide in from left
          'fixed top-0 left-0 z-30 tablet:relative tablet:z-auto tablet:translate-x-0',
          isOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Logo */}
        <div className="px-5 py-5 border-b border-primary-800">
          <div className="flex items-center gap-3">
            <img
              src="/icons/medical-cross.svg"
              alt="ClinNote AI"
              className="h-8 w-8 rounded-lg"
            />
            <div>
              <p className="text-base font-bold text-white tracking-tight">ClinNote AI</p>
              <p className="text-xs text-teal-400 font-medium">Ambient Clinical Documentation</p>
            </div>
          </div>

          {/* AI status pill */}
          <div
            className={clsx(
              'mt-4 inline-flex items-center gap-2 px-2.5 py-1 rounded-full',
              'bg-teal-900/30 border border-teal-700/40 text-teal-300 text-[10px] font-semibold'
            )}
            aria-live="polite"
          >
            <span className="relative inline-flex h-2 w-2" aria-hidden="true">
              <span className="absolute inset-0 rounded-full bg-teal-400 opacity-70 animate-ping" />
              <span className="relative h-2 w-2 rounded-full bg-teal-400" />
            </span>
            <span className="uppercase tracking-wider">AI Online</span>
          </div>
        </div>

        {/* Navigation items */}
        <div className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
          {visibleItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={onClose}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-3 rounded-lg text-sm font-medium',
                  'transition-all duration-150',
                  'min-h-[44px]',
                  'focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-inset',
                  isActive
                    ? 'bg-primary-700 text-white shadow-sm border border-primary-600'
                    : 'text-gray-400 hover:text-white hover:bg-primary-800'
                )
              }
            >
              {item.icon}
              {item.label}
              {item.badge !== undefined && item.badge > 0 && (
                <span className="ml-auto flex h-5 min-w-[20px] items-center justify-center rounded-full bg-red-600 text-xs text-white px-1">
                  {item.badge}
                </span>
              )}
            </NavLink>
          ))}
        </div>

        {/* User info + logout at bottom */}
        {user && (
          <div className="border-t border-primary-800 p-4 space-y-3">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-700 text-sm font-semibold text-teal-300">
                {user.full_name.charAt(0)}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-gray-200 truncate">{user.full_name}</p>
                <span
                  className={clsx(
                    'mt-0.5 inline-flex items-center px-1.5 h-4 rounded border text-[10px] font-semibold uppercase tracking-wider',
                    roleClass
                  )}
                >
                  {user.role.replace('_', ' ')}
                </span>
              </div>
            </div>
            <button
              onClick={() => logout()}
              className={clsx(
                'flex items-center gap-2 w-full px-3 py-2 rounded-lg text-sm',
                'text-gray-400 hover:text-white hover:bg-primary-800 transition-colors',
                'min-h-[40px] focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-inset'
              )}
              aria-label="Log out of ClinNote AI"
            >
              <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
              Log Out
            </button>
          </div>
        )}
      </nav>
    </>
  );
};
