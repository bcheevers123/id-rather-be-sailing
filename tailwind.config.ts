import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Semantic CSS-variable tokens — use as text-ink, bg-surface, etc.
        ink:           'var(--ink)',
        'ink-muted':   'var(--ink-muted)',
        'ink-faint':   'var(--ink-faint)',
        surface:       'var(--surface)',
        'surface-2':   'var(--surface-2)',
        'surface-3':   'var(--surface-3)',
        border:        'var(--border)',
        'border-strong': 'var(--border-strong)',
        accent:        'var(--accent)',
        'accent-dim':  'var(--accent-dim)',
        'accent-tint': 'var(--accent-tint)',
        phosphor:      'var(--phosphor)',
        // Water ramp for direct use
        water: {
          900: 'var(--water-900)',
          800: 'var(--water-800)',
          700: 'var(--water-700)',
          600: 'var(--water-600)',
          500: 'var(--water-500)',
          400: 'var(--water-400)',
          300: 'var(--water-300)',
          200: 'var(--water-200)',
          100: 'var(--water-100)',
          50:  'var(--water-50)',
        },
      },
      borderColor: {
        DEFAULT: 'var(--border)',
        strong:  'var(--border-strong)',
      },
      fontFamily: {
        data: 'var(--font-data)',
        ui:   'var(--font-ui)',
      },
    },
  },
  plugins: [],
} satisfies Config
