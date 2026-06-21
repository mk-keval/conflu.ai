import type { Config } from 'tailwindcss';

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        dark: {
          50: '#C9D1D9',
          100: '#B1BAC4',
          200: '#8B949E',
          300: '#6E7681',
          400: '#484F58',
          500: '#30363D',
          600: '#21262D',
          700: '#161B22',
          800: '#0D1117',
          900: '#010409',
        },
        accent: {
          DEFAULT: '#7B68EE',
          light: '#9B8BF4',
          dark: '#5A4DD6',
        },
        gain: '#22C55E',
        loss: '#EF4444',
        volume: '#60A5FA',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
} satisfies Config;
