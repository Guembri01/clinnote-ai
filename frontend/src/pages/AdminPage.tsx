/**
 * AdminPage for ClinNote AI
 *
 * Admin-only: active sessions, audit logs, system usage stats, user list.
 */

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AdminDashboard } from '@/components/organisms/AdminDashboard';
import { AuditLogTable } from '@/components/organisms/AuditLogTable';
import { Badge } from '@/components/atoms/Badge';
import { listUsers, type AdminUser } from '@/api/admin';
import { formatDate } from '@/utils/formatters';
import { clsx } from 'clsx';

type AdminTab = 'dashboard' | 'audit' | 'users';

/**
 * Admin Management Page
 */
export const AdminPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<AdminTab>('dashboard');

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Administration</h1>
        <p className="text-gray-400 text-sm mt-1">System monitoring and HIPAA compliance</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-primary-700" role="tablist">
        {(
          [
            { id: 'dashboard' as AdminTab, label: 'Live Dashboard' },
            { id: 'audit' as AdminTab, label: 'Audit Log' },
            { id: 'users' as AdminTab, label: 'Users' },
          ] as const
        ).map((tab) => (
          <button
            key={tab.id}
            role="tab"
            id={`tab-${tab.id}`}
            aria-selected={activeTab === tab.id}
            aria-controls={`panel-${tab.id}`}
            onClick={() => setActiveTab(tab.id)}
            className={clsx(
              'px-5 py-3 text-sm font-medium border-b-2 transition-colors -mb-px min-h-[44px]',
              activeTab === tab.id
                ? 'border-teal-500 text-white'
                : 'border-transparent text-gray-400 hover:text-gray-200 hover:border-primary-600'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab panels */}
      <div
        id="panel-dashboard"
        role="tabpanel"
        aria-labelledby="tab-dashboard"
        hidden={activeTab !== 'dashboard'}
      >
        {activeTab === 'dashboard' && <AdminDashboard />}
      </div>

      <div
        id="panel-audit"
        role="tabpanel"
        aria-labelledby="tab-audit"
        hidden={activeTab !== 'audit'}
      >
        {activeTab === 'audit' && (
          <div>
            <div className="flex items-center gap-2 mb-4 p-3 rounded-lg bg-amber-900/20 border border-amber-700/40">
              <svg className="h-4 w-4 text-amber-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <p className="text-xs text-amber-300">
                HIPAA Audit Log — all PHI access events are recorded and immutable
              </p>
            </div>
            <AuditLogTable />
          </div>
        )}
      </div>

      <div
        id="panel-users"
        role="tabpanel"
        aria-labelledby="tab-users"
        hidden={activeTab !== 'users'}
      >
        {activeTab === 'users' && <UsersPanel />}
      </div>
    </div>
  );
};

/** Users tab — admin-scope user table */
const UsersPanel: React.FC = () => {
  const { data, isLoading } = useQuery({
    queryKey: ['admin', 'users'],
    queryFn: listUsers,
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading) {
    return (
      <div className="space-y-2" aria-label="Loading users">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="h-12 rounded-lg bg-primary-800/40 border border-primary-700/40 animate-pulse"
          />
        ))}
      </div>
    );
  }

  const users: AdminUser[] = data ?? [];

  if (users.length === 0) {
    return (
      <div className="rounded-lg border border-primary-700 bg-primary-900/40 p-10 text-center">
        <p className="text-sm text-gray-400">No users found.</p>
      </div>
    );
  }

  const roleVariant = (role: string) =>
    role === 'admin' ? 'warning' : role === 'physician' ? 'teal' : 'info';

  return (
    <div className="overflow-x-auto rounded-lg border border-primary-700">
      <table className="min-w-full text-sm">
        <thead className="bg-primary-800/60 text-gray-300 text-left text-xs uppercase tracking-wider">
          <tr>
            <th className="px-4 py-3 font-semibold">Name</th>
            <th className="px-4 py-3 font-semibold">Email</th>
            <th className="px-4 py-3 font-semibold">Role</th>
            <th className="px-4 py-3 font-semibold">Specialty</th>
            <th className="px-4 py-3 font-semibold">MFA</th>
            <th className="px-4 py-3 font-semibold">Status</th>
            <th className="px-4 py-3 font-semibold">Created</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-primary-800">
          {users.map((u) => (
            <tr key={u.id} className="text-gray-200 hover:bg-primary-800/30">
              <td className="px-4 py-3 whitespace-nowrap">
                {u.first_name} {u.last_name}
              </td>
              <td className="px-4 py-3 text-gray-300">{u.email}</td>
              <td className="px-4 py-3">
                <Badge variant={roleVariant(u.role)} size="sm">
                  {u.role}
                </Badge>
              </td>
              <td className="px-4 py-3 text-gray-400">{u.specialty ?? '—'}</td>
              <td className="px-4 py-3">
                <span
                  className={clsx(
                    'inline-block h-2.5 w-2.5 rounded-full',
                    u.totp_enabled ? 'bg-green-400' : 'bg-gray-500'
                  )}
                  aria-label={u.totp_enabled ? 'MFA enabled' : 'MFA disabled'}
                />
              </td>
              <td className="px-4 py-3">
                <Badge variant={u.is_active ? 'success' : 'muted'} size="sm">
                  {u.is_active ? 'Active' : 'Inactive'}
                </Badge>
              </td>
              <td className="px-4 py-3 text-gray-400 whitespace-nowrap">
                {formatDate(u.created_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
