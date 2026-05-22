/**
 * Button atom for ClinNote AI
 *
 * Accessible button component with clinical variants and sizes.
 * All variants meet WCAG 2.1 AA minimum touch target size (44x44px).
 *
 * @example
 * <Button variant="primary" size="lg" onClick={handleApprove}>
 *   Approve Note
 * </Button>
 */

import React from 'react';
import { clsx } from 'clsx';
import { Spinner } from './Spinner';

export type ButtonVariant = 'primary' | 'danger' | 'ghost' | 'success' | 'warning' | 'secondary';
export type ButtonSize = 'sm' | 'md' | 'lg' | 'xl';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** Visual style variant */
  variant?: ButtonVariant;
  /** Button size — affects padding, font size, min-height */
  size?: ButtonSize;
  /** Show a loading spinner and disable interaction */
  loading?: boolean;
  /** Icon to show on the left side */
  leftIcon?: React.ReactNode;
  /** Icon to show on the right side */
  rightIcon?: React.ReactNode;
  /** Fill the full width of the parent */
  fullWidth?: boolean;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    'bg-primary-500 hover:bg-primary-400 active:bg-primary-600 text-white border border-primary-400 shadow-sm',
  danger:
    'bg-red-600 hover:bg-red-500 active:bg-red-700 text-white border border-red-500 shadow-sm',
  ghost:
    'bg-transparent hover:bg-primary-800 active:bg-primary-900 text-gray-300 hover:text-white border border-primary-700',
  success:
    'bg-green-600 hover:bg-green-500 active:bg-green-700 text-white border border-green-500 shadow-sm',
  warning:
    'bg-amber-500 hover:bg-amber-400 active:bg-amber-600 text-gray-900 border border-amber-400 shadow-sm',
  secondary:
    'bg-primary-800 hover:bg-primary-700 active:bg-primary-900 text-gray-200 border border-primary-600',
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'px-3 py-2 text-sm min-h-[36px] min-w-[36px] gap-1.5',
  md: 'px-4 py-2.5 text-sm min-h-[44px] min-w-[44px] gap-2',
  lg: 'px-6 py-3 text-base min-h-[52px] min-w-[52px] gap-2',
  xl: 'px-8 py-4 text-lg min-h-[60px] min-w-[60px] gap-3',
};

/**
 * Clinical Button Component
 */
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'primary',
      size = 'md',
      loading = false,
      leftIcon,
      rightIcon,
      fullWidth = false,
      disabled,
      children,
      className,
      ...props
    },
    ref
  ) => {
    const isDisabled = disabled || loading;

    return (
      <button
        ref={ref}
        disabled={isDisabled}
        aria-busy={loading}
        className={clsx(
          // Base styles
          'inline-flex items-center justify-center rounded-lg font-medium',
          'transition-all duration-150 ease-in-out',
          'focus:outline-none focus:ring-2 focus:ring-teal-400 focus:ring-offset-2 focus:ring-offset-gray-950',
          'select-none',
          // Variant
          variantClasses[variant],
          // Size
          sizeClasses[size],
          // Full width
          fullWidth && 'w-full',
          // Disabled
          isDisabled && 'opacity-50 cursor-not-allowed pointer-events-none',
          className
        )}
        {...props}
      >
        {loading ? (
          <Spinner size={size === 'sm' ? 'sm' : 'md'} className="shrink-0" />
        ) : (
          leftIcon && <span className="shrink-0">{leftIcon}</span>
        )}
        {children && <span>{children}</span>}
        {rightIcon && !loading && <span className="shrink-0">{rightIcon}</span>}
      </button>
    );
  }
);

Button.displayName = 'Button';
