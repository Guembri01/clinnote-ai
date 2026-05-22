/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          950: '#060d1c',
          900: '#0F1B35',
          800: '#1a2a4a',
          700: '#1e3a5f',
          600: '#1a5280',
          500: '#1d6fa4',
          400: '#2b8cc4',
          300: '#5ba3d0',
          200: '#93c5e8',
          100: '#cce3f4',
          50:  '#e8f4fb',
        },
        teal: {
          600: '#0c8a7e',
          500: '#0f9b8e',
          400: '#14b8a6',
          300: '#2dd4bf',
          200: '#99f6e4',
          100: '#ccfbf1',
        },
        clinical: {
          bg: '#030712',
          surface: '#0a1628',
          border: '#1e3a5f',
          text: '#e2e8f0',
          muted: '#94a3b8',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Menlo', 'monospace'],
      },
      animation: {
        'pulse-ring': 'pulse-ring 1.5s cubic-bezier(0.215, 0.61, 0.355, 1) infinite',
        'spin-slow': 'spin 3s linear infinite',
        'bounce-subtle': 'bounce-subtle 1s ease-in-out infinite',
        'fade-in': 'fade-in 0.2s ease-out',
        'slide-in-right': 'slide-in-right 0.3s ease-out',
        'slide-in-up': 'slide-in-up 0.3s ease-out',
        'audio-bar': 'audio-bar 0.8s ease-in-out infinite alternate',
      },
      keyframes: {
        'pulse-ring': {
          '0%': { transform: 'scale(0.95)', boxShadow: '0 0 0 0 rgba(220, 38, 38, 0.7)' },
          '70%': { transform: 'scale(1)', boxShadow: '0 0 0 15px rgba(220, 38, 38, 0)' },
          '100%': { transform: 'scale(0.95)', boxShadow: '0 0 0 0 rgba(220, 38, 38, 0)' },
        },
        'bounce-subtle': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-4px)' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'slide-in-right': {
          '0%': { transform: 'translateX(100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        'slide-in-up': {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        'audio-bar': {
          '0%': { height: '20%' },
          '100%': { height: '100%' },
        }
      },
      minHeight: {
        'touch': '44px',
      },
      minWidth: {
        'touch': '44px',
      },
      screens: {
        'tablet': '768px',
        'desktop': '1280px',
      }
    },
  },
  plugins: [],
}
