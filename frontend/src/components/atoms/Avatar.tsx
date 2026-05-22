/**
 * Avatar atom for ClinNote AI
 *
 * User avatar with initials fallback and optional status indicator.
 *
 * @example
 * <Avatar name="Dr. Sarah Chen" src={user.avatar_url} size="md" />
 */

import React from 'react';
import { clsx } from 'clsx';

export type AvatarSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

export interface AvatarProps {
  /** Full name — used to generate initials */
  name: string;
  /** Optional avatar image URL */
  src?: string;
  /** Size variant */
  size?: AvatarSize;
  /** Optional CSS classes */
  className?: string;
  /** Show online/offline status indicator */
  status?: 'online' | 'offline' | 'busy';
}

const sizeClasses: Record<AvatarSize, { container: string; text: string; indicator: string }> = {
  xs: { container: 'h-6 w-6', text: 'text-xs', indicator: 'h-1.5 w-1.5 border' },
  sm: { container: 'h-8 w-8', text: 'text-xs', indicator: 'h-2 w-2 border' },
  md: { container: 'h-10 w-10', text: 'text-sm', indicator: 'h-2.5 w-2.5 border' },
  lg: { container: 'h-12 w-12', text: 'text-base', indicator: 'h-3 w-3 border-2' },
  xl: { container: 'h-16 w-16', text: 'text-xl', indicator: 'h-4 w-4 border-2' },
};

const statusColors = {
  online: 'bg-green-400',
  offline: 'bg-gray-500',
  busy: 'bg-amber-400',
};

/** Generate initials from a full name */
function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].charAt(0).toUpperCase();
  return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
}

/** Generate a consistent color from a name */
function getAvatarColor(name: string): string {
  const colors = [
    'bg-primary-600',
    'bg-teal-600',
    'bg-purple-600',
    'bg-indigo-600',
    'bg-cyan-700',
    'bg-sky-700',
  ];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}

/**
 * Clinical User Avatar
 */
export const Avatar: React.FC<AvatarProps> = ({
  name,
  src,
  size = 'md',
  className,
  status,
}) => {
  const sizes = sizeClasses[size];
  const initials = getInitials(name);
  const bgColor = getAvatarColor(name);

  return (
    <span className={clsx('relative inline-flex shrink-0', className)}>
      {src ? (
        <img
          src={src}
          alt={name}
          className={clsx('rounded-full object-cover ring-2 ring-primary-700', sizes.container)}
        />
      ) : (
        <span
          aria-label={name}
          className={clsx(
            'flex items-center justify-center rounded-full font-semibold text-white',
            'ring-2 ring-primary-700',
            bgColor,
            sizes.container,
            sizes.text
          )}
        >
          {initials}
        </span>
      )}

      {status && (
        <span
          aria-label={`Status: ${status}`}
          className={clsx(
            'absolute bottom-0 right-0 rounded-full border-gray-950',
            statusColors[status],
            sizes.indicator
          )}
        />
      )}
    </span>
  );
};
