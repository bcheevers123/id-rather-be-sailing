import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
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
        paper:         'var(--paper)',
        'paper-sea':   'var(--paper-sea)',
        'paper-deep':  'var(--paper-deep)',
        soundings:     'var(--soundings)',
        navy: {
          950: 'var(--navy-950)',
          900: 'var(--navy-900)',
          800: 'var(--navy-800)',
          600: 'var(--navy-600)',
          400: 'var(--navy-400)',
          200: 'var(--navy-200)',
          100: 'var(--navy-100)',
          50:  'var(--navy-50)',
        },
      },
      borderColor: {
        DEFAULT: 'var(--border)',
        strong:  'var(--border-strong)',
      },
      fontFamily: {
        ui:   'var(--font-ui)',
        sans: 'var(--font-sans)',
        data: 'var(--font-data)',
      },
    },
  },
  plugins: [],
} satisfies Config
