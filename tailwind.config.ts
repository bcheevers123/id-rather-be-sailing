import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Legacy navy kept for any remaining references
        navy: {
          50:  '#f0f4ff',
          100: '#e0e9ff',
          600: '#1e3a6e',
          700: '#162d5a',
          800: '#0f2044',
          900: '#081530',
        },
        // CSS-variable tokens — use as text-ink, bg-surface-2, etc.
        ink:      'var(--ink)',
        'ink-muted':  'var(--ink-muted)',
        'ink-faint':  'var(--ink-faint)',
        surface:  'var(--surface)',
        'surface-2': 'var(--surface-2)',
        'surface-3': 'var(--surface-3)',
        border:   'var(--border)',
        accent:   'var(--accent)',
        'accent-dim': 'var(--accent-dim)',
        'accent-tint': 'var(--accent-tint)',
      },
      borderColor: {
        DEFAULT: 'var(--border)',
        strong:  'var(--border-strong)',
      },
    },
  },
  plugins: [],
} satisfies Config
