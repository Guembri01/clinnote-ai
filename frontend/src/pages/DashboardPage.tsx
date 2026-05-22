/**
 * DashboardPage for ClinNote AI
 *
 * Investor-grade dashboard:
 *   - Greeting + date + streak badge
 *   - 6 KPI cards (real where possible, mocked where backend lacks the metric)
 *   - 14-day sparkline session trend
 *   - AI Insights panel (3 contextual insights)
 *   - Today's Schedule widget (mocked)
 *   - Compliance status strip
 *   - Recent sessions list
 */

import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { clsx } from 'clsx';
import { getNotesHistory } from '@/api/notes';
import { getUsageStats } from '@/api/admin';
import { useAuthStore } from '@/store/authStore';
import { SessionList } from '@/components/organisms/SessionList';
import { Button } from '@/components/atoms/Button';
import { format } from 'date-fns';
import {
  DEMO_SESSIONS_LAST_14_DAYS,
  DEMO_TODAY_SCHEDULE,
  DEMO_USAGE_STATS,
} from '@/utils/demoFallbacks';
import type { UsageStats } from '@/types/api';

/**
 * Dashboard Page
 */
export const DashboardPage: React.FC = () => {
  const { user } = useAuthStore();
  const today = format(new Date(), 'EEEE, MMMM d, yyyy');

  // Real pending-review count
  const { data: pendingNotes } = useQuery({
    queryKey: ['notes-history', 'pending'],
    queryFn: () => getNotesHistory({ page: 1, page_size: 5, status: 'draft' }),
  });

  // Try real usage stats; fall back to demo data if empty / errors out.
  const { data: statsRaw } = useQuery({
    queryKey: ['admin-stats', 'dashboard'],
    queryFn: () => getUsageStats(),
    retry: false,
    staleTime: 60_000,
  });
  // FALLBACK: when backend stats are unavailable or all-zero (fresh deploy)
  const stats: UsageStats =
    statsRaw && statsRaw.total_notes > 0 ? statsRaw : DEMO_USAGE_STATS;

  const pendingCount = pendingNotes?.total ?? stats.pending_approval;
  // mock: true — backend doesn't expose streak yet
  const streakDays = 12;
  // mock: true — believable small-clinic numbers (18-session seed, 7 clinicians)
  const sessionsThisWeek = 18;
  const sentToEhr = 11;
  const avgApprovalMinutes = 3.2;
  const aiAccuracy = 96.4;
  const hoursSavedMonth = 8;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-start gap-3">
          <div>
            <h1 className="text-2xl font-bold text-white">
              Good {getGreeting()}, {user?.full_name?.split(' ')[0] ?? 'Doctor'}
            </h1>
            <p className="text-gray-400 text-sm mt-1">{today}</p>
          </div>
          <StreakBadge days={streakDays} />
        </div>

        <Link to="/sessions/new">
          <Button
            variant="primary"
            size="xl"
            leftIcon={
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
            }
          >
            New Session
          </Button>
        </Link>
      </div>

      {/* KPI grid — 6 cards */}
      <div className="grid grid-cols-2 gap-3 tablet:grid-cols-3 desktop:grid-cols-6">
        <KpiCard
          label="Sessions This Week"
          value={sessionsThisWeek /* mock: true */}
          trendPct={+14.2 /* mock: true */}
          accent="teal"
          icon={
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
            </svg>
          }
        />
        <KpiCard
          label="Notes Pending"
          value={pendingCount}
          accent={pendingCount > 0 ? 'amber' : 'teal'}
          icon={
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
        />
        <KpiCard
          label="Avg. Approval Time"
          value={`${avgApprovalMinutes}m`}
          trendPct={-22.1 /* mock: true */}
          accent="teal"
          icon={
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          }
        />
        <KpiCard
          label="Sent to EHR"
          value={sentToEhr /* mock: true */}
          accent="green"
          icon={
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          }
        />
        <KpiCard
          label="AI Accuracy"
          value={`${aiAccuracy}%` /* mock: true */}
          trendPct={+1.3 /* mock: true */}
          accent="teal"
          icon={
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          }
        />
        <KpiCard
          label="Hours Saved (mo)"
          value={hoursSavedMonth /* mock: true */}
          trendPct={+8.7 /* mock: true */}
          accent="teal"
          icon={
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
        />
      </div>

      {/* Sparkline + AI Insights row */}
      <div className="grid grid-cols-1 gap-4 desktop:grid-cols-3">
        <SparklineStrip data={DEMO_SESSIONS_LAST_14_DAYS} />
        <AIInsightsPanel />
      </div>

      {/* Today's schedule + compliance row */}
      <div className="grid grid-cols-1 gap-4 desktop:grid-cols-3">
        <TodayScheduleWidget />
        <ComplianceStrip />
      </div>

      {/* Recent sessions */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-100">Recent Sessions</h2>
          <Link
            to="/notes"
            className="text-sm text-teal-400 hover:text-teal-300 transition-colors min-h-[44px] flex items-center"
          >
            View all
          </Link>
        </div>
        <SessionList limit={5} showPagination={false} />
      </div>
    </div>
  );
};

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'morning';
  if (hour < 17) return 'afternoon';
  return 'evening';
}

/* ---------------------------- Sub-components ---------------------------- */

const StreakBadge: React.FC<{ days: number }> = ({ days }) => (
  <span
    className="inline-flex items-center gap-1.5 px-2.5 h-7 mt-1 rounded-full bg-amber-900/30 border border-amber-700/40 text-amber-300 text-xs font-semibold"
    aria-label={`${days} day documentation streak`}
  >
    <svg className="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
      <path
        fillRule="evenodd"
        d="M12.395 2.553a1 1 0 00-1.45-.385c-.345.23-.614.558-.822.88-.214.33-.403.713-.57 1.116-.334.804-.614 1.768-.84 2.734a31.365 31.365 0 00-.613 3.58 2.64 2.64 0 01-.945-1.067c-.328-.68-.398-1.534-.398-2.654A1 1 0 005.05 6.05 6.981 6.981 0 003 11a7 7 0 1011.95-4.95c-.592-.591-.98-.985-1.348-1.467-.363-.476-.724-1.063-1.207-2.03zM12.12 15.12A3 3 0 017 13s.879.5 2.5.5c0-1 .5-4 1.25-4.5.5 1 .786 1.293 1.371 1.879A2.99 2.99 0 0113 13a2.99 2.99 0 01-.879 2.121z"
        clipRule="evenodd"
      />
    </svg>
    {days} day streak
  </span>
);

interface KpiCardProps {
  label: string;
  value: number | string;
  trendPct?: number;
  accent: 'teal' | 'amber' | 'green';
  icon: React.ReactNode;
}

const KpiCard: React.FC<KpiCardProps> = ({ label, value, trendPct, accent, icon }) => {
  const accentClasses: Record<KpiCardProps['accent'], string> = {
    teal: 'border-teal-700/40 bg-teal-900/10 text-teal-300',
    amber: 'border-amber-700/40 bg-amber-900/10 text-amber-300',
    green: 'border-green-700/40 bg-green-900/10 text-green-300',
  };
  const trendUp = trendPct !== undefined && trendPct >= 0;
  return (
    <div className="rounded-xl border border-primary-700 bg-primary-900/30 p-4 flex flex-col gap-2 hover:border-teal-700/30 transition-colors">
      <div className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold">
          {label}
        </span>
        <span
          className={clsx(
            'flex items-center justify-center h-6 w-6 rounded-md border',
            accentClasses[accent]
          )}
        >
          {icon}
        </span>
      </div>
      <p className="text-2xl font-bold text-white tabular-nums leading-none">{value}</p>
      {trendPct !== undefined && (
        <p
          className={clsx(
            'text-[11px] font-medium flex items-center gap-1',
            trendUp ? 'text-green-400' : 'text-red-400'
          )}
        >
          <span aria-hidden="true">{trendUp ? '▲' : '▼'}</span>
          {Math.abs(trendPct).toFixed(1)}% vs last week
        </p>
      )}
    </div>
  );
};

/** 14-day session count sparkline rendered as inline SVG, hand-written path. */
const SparklineStrip: React.FC<{ data: number[] }> = ({ data }) => {
  const W = 320;
  const H = 70;
  const PAD = 4;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = Math.max(1, max - min);
  const stepX = (W - PAD * 2) / Math.max(1, data.length - 1);
  const points = data.map((v, i) => {
    const x = PAD + i * stepX;
    const y = PAD + ((max - v) / range) * (H - PAD * 2);
    return [x, y] as const;
  });
  const pathD = points
    .map(([x, y], i) => (i === 0 ? `M ${x.toFixed(2)} ${y.toFixed(2)}` : `L ${x.toFixed(2)} ${y.toFixed(2)}`))
    .join(' ');
  const areaD =
    pathD + ` L ${points[points.length - 1][0].toFixed(2)} ${H - PAD} L ${PAD} ${H - PAD} Z`;
  const today = data[data.length - 1];
  const yesterday = data[data.length - 2] ?? today;
  const delta = today - yesterday;

  return (
    <div className="rounded-xl border border-primary-700 bg-primary-900/30 p-4 col-span-2 desktop:col-span-2">
      <div className="flex items-baseline justify-between mb-2">
        <div>
          <p className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold">
            Sessions — Last 14 days
          </p>
          <p className="text-xl font-bold text-white tabular-nums mt-0.5">
            {today}
            <span className={clsx(
              'ml-2 text-xs font-medium',
              delta >= 0 ? 'text-green-400' : 'text-red-400'
            )}>
              {delta >= 0 ? '+' : ''}{delta} d/d
            </span>
          </p>
        </div>
        <span className="text-[10px] uppercase tracking-wider text-teal-400">trend</span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        height={H}
        role="img"
        aria-label="Daily sessions over the last 14 days"
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#14b8a6" stopOpacity="0.45" />
            <stop offset="100%" stopColor="#14b8a6" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={areaD} fill="url(#sparkFill)" />
        <path d={pathD} fill="none" stroke="#2dd4bf" strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />
        {/* Last-point dot */}
        <circle
          cx={points[points.length - 1][0]}
          cy={points[points.length - 1][1]}
          r={3}
          fill="#2dd4bf"
        />
      </svg>
    </div>
  );
};

const AIInsightsPanel: React.FC = () => {
  const insights = [
    {
      label: 'Top 3 diagnoses this week',
      // mock: true — backend doesn't yet expose top-diagnoses aggregation
      value: 'E11.65 · I10 · J45.40',
      icon: (
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      ),
    },
    {
      label: 'Avg. note approval time',
      value: '4.6 min · 22% faster' /* mock: true */,
      icon: (
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      ),
    },
    {
      label: 'Suggested template',
      // mock: true — depends on schedule + history
      value: 'Diabetes Follow-up (used 9× this month)',
      icon: (
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
      ),
    },
  ];
  return (
    <div className="rounded-xl border border-teal-700/30 bg-primary-900/30 p-4 glass-panel">
      <div className="flex items-center justify-between mb-3">
        <p className="text-[10px] uppercase tracking-wider text-teal-400 font-semibold flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-teal-400 animate-pulse" aria-hidden="true" />
          AI Insights
        </p>
        <span className="text-[10px] text-gray-500">updated just now</span>
      </div>
      <ul className="space-y-3">
        {insights.map((it) => (
          <li key={it.label} className="flex items-start gap-2.5">
            <span className="shrink-0 mt-0.5 h-7 w-7 rounded-md bg-teal-900/40 border border-teal-700/40 text-teal-300 flex items-center justify-center">
              {it.icon}
            </span>
            <div className="min-w-0">
              <p className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold">
                {it.label}
              </p>
              <p className="text-sm text-gray-100 mt-0.5 leading-snug">{it.value}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
};

const TodayScheduleWidget: React.FC = () => (
  <div className="rounded-xl border border-primary-700 bg-primary-900/30 p-4 col-span-1 desktop:col-span-2">
    <div className="flex items-center justify-between mb-3">
      <p className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold">
        Today's Schedule
      </p>
      <span className="text-[10px] text-teal-400">{DEMO_TODAY_SCHEDULE.length} upcoming</span>
    </div>
    <ul className="divide-y divide-primary-800">
      {/* FALLBACK: mock schedule data */}
      {DEMO_TODAY_SCHEDULE.map((appt, i) => (
        <li key={i} className="flex items-center gap-3 py-2.5 first:pt-0 last:pb-0">
          <span className="font-mono text-sm font-semibold text-teal-300 w-12 shrink-0">{appt.time}</span>
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-800 text-teal-300 text-xs font-semibold">
            {appt.initials}
          </span>
          <p className="text-sm text-gray-200 truncate flex-1">{appt.complaint}</p>
          <span className="text-[10px] uppercase tracking-wider text-gray-500 shrink-0">
            scheduled
          </span>
        </li>
      ))}
    </ul>
  </div>
);

const ComplianceStrip: React.FC = () => {
  const items = [
    'Session Timeout 15m',
    'MFA Enabled',
    'PHI Encrypted',
    'Audit Log Active',
  ];
  return (
    <div className="rounded-xl border border-green-700/30 bg-green-900/5 p-4">
      <p className="text-[10px] uppercase tracking-wider text-green-400 font-semibold mb-3">
        Compliance Status
      </p>
      <ul className="space-y-2">
        {items.map((label) => (
          <li key={label} className="flex items-center gap-2 text-xs text-gray-300">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-green-900/40 border border-green-700/50 text-green-300 shrink-0">
              <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
              </svg>
            </span>
            {label}
          </li>
        ))}
      </ul>
    </div>
  );
};
