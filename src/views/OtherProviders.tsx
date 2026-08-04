import { useMemo, useState, useCallback } from 'react'
import { useData } from '../hooks/useData'
import { safeHref } from '../lib/safeHref'

function ExternalLinkIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
      style={{ flexShrink: 0 }}>
      <path d="M7 3H3a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1V9"/>
      <polyline points="10 1 15 1 15 6"/>
      <line x1="15" y1="1" x2="7" y2="9"/>
    </svg>
  )
}

function PhoneIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor"
      strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M14 11.5A11.8 11.8 0 0 1 9.9 14c-5 0-9-4-9-9A11.8 11.8 0 0 1 3.5 1l2 4-1.5 1.5a10.5 10.5 0 0 0 4.5 4.5L10 9.5l4 2z"/>
    </svg>
  )
}

function MailIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor"
      strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="1" y="3" width="14" height="10" rx="1"/>
      <polyline points="1 3 8 9 15 3"/>
    </svg>
  )
}

type LocationGroup = { label: string; providers: ReturnType<typeof useData>['providers'] }

export function OtherProviders() {
  const { providers, offerings, loading, error } = useData()
  const [query, setQuery] = useState('')
  const [showOverseas, setShowOverseas] = useState(false)

  const activeIds = useMemo(
    () => new Set(offerings.map(o => o.provider_id)),
    [offerings]
  )

  const inactive = useMemo(
    () => providers.filter(p => !activeIds.has(p.id)),
    [providers, activeIds]
  )

  const filtered = useMemo(() => {
    let list = showOverseas ? inactive : inactive.filter(p => p.country === 'GB' || (p.country === null && isUkRegion(p.region)))
    if (query.trim()) {
      const q = query.toLowerCase()
      list = list.filter(p =>
        p.official_name.toLowerCase().includes(q) ||
        (p.region ?? '').toLowerCase().includes(q) ||
        (p.city ?? '').toLowerCase().includes(q)
      )
    }
    return list
  }, [inactive, query, showOverseas])

  const grouped = useMemo((): LocationGroup[] => {
    const map = new Map<string, typeof filtered>()
    for (const p of filtered) {
      const key = p.region ?? p.city ?? 'Other'
      const arr = map.get(key) ?? []
      arr.push(p)
      map.set(key, arr)
    }
    return Array.from(map.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([label, ps]) => ({ label, providers: ps.sort((a, b) => a.official_name.localeCompare(b.official_name)) }))
  }, [filtered])

  const handleQueryChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value)
  }, [])

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-8">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {[220, 400, 300, 400, 300].map((w, i) => (
            <div key={i} className="skeleton" style={{ height: i === 0 ? 28 : 20, width: w }} />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-8" role="alert">
        <div style={{
          background: 'var(--danger-bg)',
          border: '1px solid oklch(40% 0.15 22 / 0.5)',
          borderRadius: '4px',
          padding: '1rem',
          color: 'var(--danger)',
          fontSize: '0.875rem',
          fontFamily: 'var(--font-data)',
        }}>
          {error}
        </div>
      </div>
    )
  }

  const gbCount = inactive.filter(p => p.country === 'GB' || (p.country === null && isUkRegion(p.region))).length

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      {/* Header */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--ink)', letterSpacing: '-0.02em', marginBottom: '0.5rem' }}>
          Other Providers
        </h1>
        <div style={{
          background: 'var(--paper-sea)',
          border: '1px solid var(--border)',
          borderLeft: '3px solid var(--soundings)',
          borderRadius: '2px',
          padding: '0.875rem 1rem',
          fontSize: '0.8125rem',
          color: 'var(--ink-muted)',
          lineHeight: 1.65,
          maxWidth: '72ch',
        }}>
          <p style={{ margin: 0 }}>
            This site automatically checks a selection of training provider websites each night to pull in live
            dates and prices. The <strong style={{ color: 'var(--ink)' }}>{inactive.length.toLocaleString()} providers</strong> listed
            here are all MCA-approved, but we haven't yet been able to read their schedules automatically — either
            because their sites are structured in a way our tools can't yet handle, or because they don't publish
            a public schedule online.
          </p>
          <p style={{ margin: '0.5rem 0 0' }}>
            You can contact any of them directly using the details below. All have been approved by the Maritime &amp;
            Coastguard Agency.
          </p>
        </div>
      </div>

      {/* Controls */}
      <div style={{
        display: 'flex',
        gap: '0.75rem',
        marginBottom: '1.25rem',
        flexWrap: 'wrap',
        alignItems: 'center',
      }}>
        <input
          type="search"
          value={query}
          onChange={handleQueryChange}
          placeholder="Filter by name or location…"
          aria-label="Filter providers"
          style={{
            flex: '1 1 220px',
            minWidth: 0,
            padding: '0.4rem 0.65rem',
            background: 'var(--surface)',
            border: '1px solid var(--border-strong)',
            borderRadius: '2px',
            fontSize: '0.8125rem',
            fontFamily: 'var(--font-data)',
            color: 'var(--ink)',
            outline: 'none',
          }}
          className="focus:ring-2 focus:ring-[var(--chart-red)] focus:ring-offset-0"
        />
        <label style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.4rem',
          fontSize: '0.78rem',
          color: 'var(--ink-muted)',
          fontFamily: 'var(--font-data)',
          cursor: 'pointer',
          userSelect: 'none',
          whiteSpace: 'nowrap',
        }}>
          <input
            type="checkbox"
            checked={showOverseas}
            onChange={e => setShowOverseas(e.target.checked)}
            style={{ accentColor: 'var(--chart-red)', width: 14, height: 14 }}
          />
          Include overseas
        </label>
        <span style={{
          fontSize: '0.72rem',
          color: 'var(--ink-faint)',
          fontFamily: 'var(--font-data)',
          whiteSpace: 'nowrap',
        }}>
          {filtered.length} showing
          {!showOverseas && ` · ${inactive.length - gbCount} overseas hidden`}
        </span>
      </div>

      {/* Provider groups */}
      {grouped.length === 0 ? (
        <p style={{ fontSize: '0.875rem', color: 'var(--ink-faint)', padding: '1rem 0' }}>
          No providers match "{query}".
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {grouped.map(group => (
            <div key={group.label}>
              <div style={{
                fontFamily: 'var(--font-data)',
                fontSize: '0.62rem',
                fontWeight: 700,
                letterSpacing: '0.10em',
                textTransform: 'uppercase',
                color: 'var(--ink-faint)',
                marginBottom: '0.375rem',
                paddingBottom: '0.25rem',
                borderBottom: '1px solid var(--border)',
              }}>
                {group.label}
                <span style={{ fontWeight: 400, letterSpacing: '0.02em', marginLeft: '0.5rem' }}>
                  · {group.providers.length}
                </span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '0.375rem' }}>
                {group.providers.map(p => (
                  <ProviderTile key={p.id} provider={p} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ProviderTile({ provider: p }: { provider: ReturnType<typeof useData>['providers'][number] }) {
  const href = safeHref(p.website)
  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: '2px',
      padding: '0.625rem 0.75rem',
      display: 'flex',
      flexDirection: 'column',
      gap: '0.35rem',
    }}>
      <div style={{
        fontFamily: 'var(--font-ui)',
        fontWeight: 700,
        fontSize: '0.85rem',
        color: 'var(--navy-950)',
        lineHeight: 1.35,
      }}>
        {p.official_name.replace(/\n/g, ' ')}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center' }}>
        {href && (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.25rem',
              fontSize: '0.72rem',
              color: 'var(--soundings)',
              textDecoration: 'none',
              fontFamily: 'var(--font-data)',
            }}
            className="hover:underline"
          >
            Website <ExternalLinkIcon />
          </a>
        )}
        {p.telephone && (
          <a
            href={`tel:${p.telephone.replace(/\s/g, '')}`}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.25rem',
              fontSize: '0.72rem',
              color: 'var(--ink-muted)',
              textDecoration: 'none',
              fontFamily: 'var(--font-data)',
            }}
            className="hover:text-[var(--ink)]"
          >
            <PhoneIcon /> {p.telephone}
          </a>
        )}
        {p.email && !p.telephone && (
          <a
            href={`mailto:${p.email}`}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.25rem',
              fontSize: '0.72rem',
              color: 'var(--ink-muted)',
              textDecoration: 'none',
              fontFamily: 'var(--font-data)',
            }}
            className="hover:text-[var(--ink)]"
          >
            <MailIcon /> {p.email}
          </a>
        )}
        {!href && !p.telephone && !p.email && (
          <span style={{ fontSize: '0.68rem', color: 'var(--ink-faint)', fontFamily: 'var(--font-data)' }}>
            no contact details
          </span>
        )}
      </div>
    </div>
  )
}

// Known UK regions/countries to separate from international
const UK_REGIONS = new Set([
  'England', 'Scotland', 'Wales', 'Northern Ireland',
  // Counties / regions that appear in the data
  'Hampshire', 'Kent', 'Devon', 'Cornwall', 'Aberdeenshire', 'Merseyside',
  'Lancashire', 'Isle of Wight', 'Tyne and Wear', 'Shetland', 'South Yorkshire',
  'West Yorkshire', 'East Yorkshire', 'North Yorkshire', 'Dorset', 'Essex',
  'Suffolk', 'Norfolk', 'Lincolnshire', 'Cumbria', 'Cheshire', 'Argyll & Bute',
  'Highland', 'Western Isles', 'Orkney', 'Fife', 'Angus', 'Perth & Kinross',
  'Renfrewshire', 'Lanarkshire', 'Ayrshire', 'East Lothian', 'Midlothian',
  'Edinburgh', 'Glasgow', 'Aberdeen', 'Dundee', 'Inverclyde', 'Down',
  'Antrim', 'Londonderry', 'Tyrone', 'Fermanagh', 'Armagh',
  'Greater London', 'London', 'Hertfordshire', 'Surrey', 'East Sussex',
  'West Sussex', 'Berkshire', 'Wiltshire', 'Somerset', 'Gloucestershire',
  'Oxfordshire', 'Buckinghamshire', 'Northamptonshire', 'Warwickshire',
  'Worcestershire', 'Herefordshire', 'Shropshire', 'Staffordshire',
  'Derbyshire', 'Nottinghamshire', 'Leicestershire', 'Rutland',
  'Northumberland', 'County Durham', 'Cleveland', 'Teesside',
  'Humberside', 'Lincolnshire', 'Cambridgeshire', 'Bedfordshire',
  'Hertfordshire', 'Middlesex', 'Avon', 'Bristol',
  'Multi-Site', // UK national providers
  'Pembrokeshire', 'Gwynedd', 'Anglesey', 'Ceredigion', 'Swansea',
  'Cardiff', 'Newport', 'Glamorgan',
])

function isUkRegion(region: string | null): boolean {
  if (!region) return false
  return UK_REGIONS.has(region) || region.endsWith('shire') || region.endsWith('ness')
}
