import type { Config } from 'tailwindcss';

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        background: '#020617',
        surface: '#0F172A',
        'surface-elevated': '#1E293B',
        'surface-hover': '#334155',
        border: '#1E293B',
        'text-primary': '#F8FAFC',
        'text-secondary': '#94A3B8',
        'text-muted': '#64748B',
        accent: {
          DEFAULT: '#22C55E',
          light: '#4ADE80',
          dark: '#16A34A',
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
        sans: ['IBM Plex Sans', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      fontSize: {
        'price': ['0.875rem', { lineHeight: '1.25rem', fontFeatureSettings: '"tnum" on' }],
        'price-lg': ['1rem', { lineHeight: '1.5rem', fontFeatureSettings: '"tnum" on' }],
      },
      boxShadow: {
        'glow-green': '0 0 20px rgba(34,197,94,0.15)',
        'glow-red': '0 0 20px rgba(239,68,68,0.15)',
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
