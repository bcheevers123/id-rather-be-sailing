import { useId } from 'react'

interface Props {
  value: string
  onChange: (value: string) => void
  placeholder?: string
}

export function SearchBar({ value, onChange, placeholder = 'Search courses…' }: Props) {
  const id = useId()
  return (
    <div className="relative w-full">
      <label htmlFor={id} className="sr-only">Search maritime training courses</label>
      <svg
        aria-hidden="true"
        width="15" height="15"
        viewBox="0 0 20 20" fill="currentColor"
        className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2"
        style={{ color: 'var(--ink-faint)' }}
      >
        <path fillRule="evenodd" d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z" clipRule="evenodd" />
      </svg>
      <input
        id={id}
        type="search"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete="off"
        spellCheck={false}
        style={{
          background: 'var(--surface)',
          color: 'var(--ink)',
          border: '1px solid var(--border-strong)',
          borderRadius: '3px',
          fontFamily: 'var(--font-sans)',
          fontSize: '0.9375rem',
          width: '100%',
          paddingLeft: '2.5rem',
          paddingRight: value ? '2.5rem' : '0.875rem',
          paddingTop: '0.55rem',
          paddingBottom: '0.55rem',
          outline: 'none',
          transition: 'border-color 120ms, box-shadow 120ms',
        }}
        className="placeholder:text-[var(--ink-faint)] focus:border-[var(--navy-600)] focus:shadow-[0_0_0_3px_oklch(94%_0.008_238)]"
      />
      {value && (
        <button
          type="button"
          onClick={() => onChange('')}
          aria-label="Clear search"
          style={{ color: 'var(--ink-faint)' }}
          className="absolute right-3 top-1/2 -translate-y-1/2 hover:text-[var(--ink)] transition-colors"
        >
          <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
            <path d="M4.22 4.22a.75.75 0 011.06 0L8 6.94l2.72-2.72a.75.75 0 111.06 1.06L9.06 8l2.72 2.72a.75.75 0 11-1.06 1.06L8 9.06l-2.72 2.72a.75.75 0 01-1.06-1.06L6.94 8 4.22 5.28a.75.75 0 010-1.06z"/>
          </svg>
        </button>
      )}
    </div>
  )
}
