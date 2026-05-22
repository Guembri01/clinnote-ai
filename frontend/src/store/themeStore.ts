/**
 * Theme Zustand store for ClinNote AI
 *
 * Persists user theme preference to localStorage. Default = dark (clinical).
 * Tailwind `darkMode: 'class'` controls the active palette; the `.theme-light`
 * override is defined in index.css. Teal accents remain constant across themes.
 */

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

export type Theme = 'dark' | 'light';

interface ThemeState {
  theme: Theme;
}

interface ThemeActions {
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

export type ThemeStore = ThemeState & ThemeActions;

export const useThemeStore = create<ThemeStore>()(
  persist(
    (set, get) => ({
      theme: 'dark',
      setTheme: (theme: Theme) => set({ theme }),
      toggleTheme: () => set({ theme: get().theme === 'dark' ? 'light' : 'dark' }),
    }),
    {
      name: 'clinnote-theme',
      storage: createJSONStorage(() => localStorage),
    }
  )
);
