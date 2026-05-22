/**
 * Input atom for ClinNote AI
 *
 * Form input with label, helper text, and error state.
 * Meets WCAG 2.1 AA accessibility requirements.
 *
 * @example
 * <Input
 *   label="Patient MRN"
 *   placeholder="123-456-789"
 *   error="MRN is required"
 *   {...register('mrn')}
 * />
 */

import React, { useState } from 'react';
import { clsx } from 'clsx';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  /** Field label */
  label?: string;
  /** Error message */
  error?: string;
  /** Helper text below the input */
  helperText?: string;
  /** Icon on the left side */
  leftIcon?: React.ReactNode;
  /** Icon on the right side */
  rightIcon?: React.ReactNode;
  /** Whether the field is required */
  required?: boolean;
}

/**
 * Eye icon for password visibility toggle
 */
const EyeIcon: React.FC<{ open: boolean }> = ({ open }) =>
  open ? (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
    </svg>
  ) : (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
    </svg>
  );

/**
 * Clinical Form Input
 */
export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  (
    {
      label,
      error,
      helperText,
      leftIcon,
      rightIcon,
      required,
      id,
      className,
      type,
      ...props
    },
    ref
  ) => {
    const fieldId = id ?? `input-${Math.random().toString(36).slice(2, 9)}`;
    const errorId = `${fieldId}-error`;
    const helperId = `${fieldId}-helper`;
    const isPasswordField = type === 'password';
    const [showPassword, setShowPassword] = useState(false);

    const resolvedType = isPasswordField ? (showPassword ? 'text' : 'password') : type;
    const hasRightSlot = rightIcon || isPasswordField;

    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label
            htmlFor={fieldId}
            className="text-sm font-medium text-gray-300"
          >
            {label}
            {required && (
              <span className="ml-1 text-red-400" aria-hidden="true">*</span>
            )}
          </label>
        )}

        <div className="relative">
          {leftIcon && (
            <span
              className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none"
              aria-hidden="true"
            >
              {leftIcon}
            </span>
          )}

          <input
            ref={ref}
            id={fieldId}
            type={resolvedType}
            aria-required={required}
            aria-invalid={!!error}
            aria-describedby={
              [error ? errorId : null, helperText ? helperId : null]
                .filter(Boolean)
                .join(' ') || undefined
            }
            className={clsx(
              'w-full rounded-lg bg-primary-900 text-gray-100 placeholder-gray-500',
              'border transition-colors duration-150',
              'px-4 py-3 text-sm',
              'min-h-[44px]',
              'focus:outline-2 focus:outline-offset-2 focus:outline-teal-400',
              'focus:outline focus:ring-0',
              leftIcon && 'pl-10',
              hasRightSlot && 'pr-10',
              error
                ? 'border-red-500 focus:border-red-400'
                : 'border-primary-700 focus:border-teal-400 hover:border-primary-500',
              className
            )}
            {...props}
          />

          {/* Password toggle button */}
          {isPasswordField && (
            <button
              type="button"
              tabIndex={-1}
              onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-200 transition-colors focus:outline-2 focus:outline-offset-1 focus:outline-teal-400 rounded"
            >
              <EyeIcon open={showPassword} />
            </button>
          )}

          {/* Custom right icon (shown only when not a password field) */}
          {!isPasswordField && rightIcon && (
            <span
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400"
              aria-hidden="true"
            >
              {rightIcon}
            </span>
          )}
        </div>

        {error && (
          <p id={errorId} role="alert" className="text-xs text-red-400 flex items-center gap-1">
            <svg className="h-3.5 w-3.5 shrink-0" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            {error}
          </p>
        )}

        {helperText && !error && (
          <p id={helperId} className="text-xs text-gray-500">
            {helperText}
          </p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';

/** Textarea variant */
export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, error, helperText, id, className, ...props }, ref) => {
    const fieldId = id ?? `textarea-${Math.random().toString(36).slice(2, 9)}`;
    const errorId = `${fieldId}-error`;

    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label htmlFor={fieldId} className="text-sm font-medium text-gray-300">
            {label}
          </label>
        )}

        <textarea
          ref={ref}
          id={fieldId}
          aria-invalid={!!error}
          aria-describedby={error ? errorId : undefined}
          className={clsx(
            'w-full rounded-lg bg-primary-900 text-gray-100 placeholder-gray-500',
            'border transition-colors duration-150',
            'px-4 py-3 text-sm resize-y min-h-[120px]',
            'focus:outline-2 focus:outline-offset-2 focus:outline-teal-400 focus:outline focus:ring-0',
            error
              ? 'border-red-500'
              : 'border-primary-700 focus:border-teal-400',
            className
          )}
          {...props}
        />

        {error && (
          <p id={errorId} role="alert" className="text-xs text-red-400">
            {error}
          </p>
        )}
        {helperText && !error && (
          <p className="text-xs text-gray-500">{helperText}</p>
        )}
      </div>
    );
  }
);

Textarea.displayName = 'Textarea';
