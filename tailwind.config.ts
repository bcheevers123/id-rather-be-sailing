import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          50: '#f0f4ff',
          100: '#e0e9ff',
          600: '#1e3a6e',
          700: '#162d5a',
          800: '#0f2044',
          900: '#081530',
        },
      },
    },
  },
  plugins: [],
} satisfies Config
