import type { Config } from 'tailwindcss';

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        background: '#05070D',
        surface: '#0A0E17',
        'surface-elevated': '#131A2A',
        'surface-hover': '#1B2436',
        'surface-tertiary': '#0D1320',
        border: 'rgba(148,163,184,0.14)',
        'text-primary': '#F1F5F9',
        'text-secondary': '#94A3B8',
        'text-muted': '#64748B',
        accent: {
          DEFAULT: '#2DD4BF',
          light: '#5EEAD4',
          dark: '#14B8A6',
        },
        gain: '#22C55E',
        'gain-bg': 'rgba(34,197,94,0.12)',
        loss: '#EF4444',
        'loss-bg': 'rgba(239,68,68,0.12)',
        volume: '#60A5FA',
        warning: '#F59E0B',
        info: '#3B82F6',
      },
      fontFamily: {
        sans: ['Manrope', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        display: ['Newsreader', 'Georgia', 'serif'],
      },
      fontSize: {
        'price': ['0.875rem', { lineHeight: '1.25rem', fontFeatureSettings: '"tnum" on' }],
        'price-lg': ['1rem', { lineHeight: '1.5rem', fontFeatureSettings: '"tnum" on' }],
      },
      boxShadow: {
        'glow-teal': '0 0 20px rgba(45,212,191,0.18)',
        'card': '0 1px 3px rgba(0,0,0,0.3), 0 1px 2px rgba(0,0,0,0.2)',
        'card-hover': '0 4px 12px rgba(0,0,0,0.4), 0 2px 4px rgba(0,0,0,0.3)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
    },
  },
  plugins: [],
} satisfies Config;
