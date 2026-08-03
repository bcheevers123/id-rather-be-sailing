import type { FilterState, DeliveryFormat, SortField } from '../types/data'

const selectStyle: React.CSSProperties = {
  width: '100%',
  background: 'var(--surface)',
  color: 'var(--ink)',
  border: '1px solid var(--border-strong)',
  borderRadius: '6px',
  padding: '0.35rem 0.6rem',
  fontSize: '0.8125rem',
  outline: 'none',
  cursor: 'pointer',
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: '0.75rem',
  fontWeight: 600,
  color: 'var(--ink-muted)',
  marginBottom: '0.35rem',
  letterSpacing: '0.01em',
}

interface Props {
  filters: FilterState
  onChange: (filters: FilterState) => void
  availableCountries: string[]
}

export function FilterPanel({ filters, onChange, availableCountries }: Props) {
  const set = (patch: Partial<FilterState>) => onChange({ ...filters, ...patch })

  const hasActiveFilters = Object.values(filters).some(v => v !== undefined)

  return (
    <aside
      aria-label="Filter results"
      style={{ display: 'flex', flexDirection: 'column', gap: '1rem', fontSize: '0.875rem' }}
    >
      <p style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--ink-muted)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
        Filters
      </p>

      <div>
        <label htmlFor="filter-country" style={labelStyle}>Country</label>
        <select
          id="filter-country"
          value={filters.country ?? ''}
          onChange={e => set({ country: e.target.value || undefined })}
          style={selectStyle}
          className="focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
        >
          <option value="">All countries</option>
          {availableCountries.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      <div>
        <label htmlFor="filter-format" style={labelStyle}>Delivery format</label>
        <select
          id="filter-format"
          value={filters.deliveryFormat ?? ''}
          onChange={e => set({ deliveryFormat: (e.target.value || undefined) as DeliveryFormat | undefined })}
          style={selectStyle}
          className="focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
        >
          <option value="">Any format</option>
          <option value="in_person">In person</option>
          <option value="blended">Blended</option>
          <option value="online">Online</option>
        </select>
      </div>

      <fieldset style={{ border: 'none', padding: 0, margin: 0 }}>
        <legend style={labelStyle}>Show only</legend>
        {[
          { key: 'hasDates' as const,  label: 'Has upcoming dates' },
          { key: 'hasPrice' as const, label: 'Has public price' },
        ].map(({ key, label }) => (
          <label
            key={key}
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', marginBottom: '0.4rem' }}
          >
            <input
              type="checkbox"
              checked={!!filters[key]}
              onChange={e => set({ [key]: e.target.checked || undefined })}
              style={{ accentColor: 'var(--accent)', width: '14px', height: '14px', cursor: 'pointer' }}
            />
            <span style={{ color: 'var(--ink)', fontSize: '0.8125rem' }}>{label}</span>
          </label>
        ))}
      </fieldset>

      <div>
        <label htmlFor="filter-sort" style={labelStyle}>Sort by</label>
        <select
          id="filter-sort"
          value={filters.sortBy ?? 'earliest_date'}
          onChange={e => set({ sortBy: e.target.value as SortField })}
          style={selectStyle}
          className="focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
        >
          <option value="earliest_date">Earliest date</option>
          <option value="lowest_price">Lowest price</option>
          <option value="provider_name">Provider name</option>
          <option value="recently_verified">Most recently verified</option>
          <option value="location">Location</option>
        </select>
      </div>

      {hasActiveFilters && (
        <button
          onClick={() => onChange({})}
          style={{
            width: '100%',
            background: 'none',
            border: '1px solid var(--border-strong)',
            borderRadius: '6px',
            padding: '0.4rem 0.75rem',
            fontSize: '0.8125rem',
            color: 'var(--ink-muted)',
            cursor: 'pointer',
            transition: 'background 100ms, color 100ms',
          }}
          className="hover:bg-[var(--surface-2)] hover:text-[var(--ink)] focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
        >
          Clear filters
        </button>
      )}
    </aside>
  )
}
