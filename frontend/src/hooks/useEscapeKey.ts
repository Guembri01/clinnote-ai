/**
 * useEscapeKey hook for ClinNote AI
 *
 * Tiny utility to close modals/drawers on Escape key.
 *
 * @example
 * useEscapeKey(onClose, isOpen);
 */

import { useEffect } from 'react';

/**
 * Adds a window keydown listener for the Escape key.
 *
 * @param onClose Callback fired when Escape is pressed.
 * @param enabled If false, the listener is not attached (useful to disable when modal is closed).
 */
export function useEscapeKey(onClose: () => void, enabled: boolean = true): void {
  useEffect(() => {
    if (!enabled) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose, enabled]);
}
