import { useMemo, useState } from 'react'
import { useData } from '../hooks/useData'
import type { Provider, Approval, Course } from '../types/data'

// Normalise the "country" field. GB providers have country="GB" but international
// providers encode their country in the region field (the PDF parser didn't populate
// country for non-UK rows). We collapse region → display name where needed.
const REGION_TO_COUNTRY: Record<string, string> = {
  'Ireland': 'Ireland',
  'France': 'France',
  'Spain': 'Spain',
  'Gibraltar': 'Gibraltar',
  'Philippines': 'Philippines',
  'Thailand': 'Thailand',
  'South Africa': 'South Africa',
  'India': 'India',
  'Trinidad\nand\nTobago': 'Trinidad & Tobago',
  'Trinidad and Tobago': 'Trinidad & Tobago',
  'Antigua\nand\nBarbuda': 'Antigua & Barbuda',
  'Antigua and Barbuda': 'Antigua & Barbuda',
  'United States of\nAmerica': 'United States',
  'United States of America': 'United States',
  'Saudi Arabia': 'Saudi Arabia',
  'United Arab Emirates': 'United Arab Emirates',
  'Malta': 'Malta',
  'Croatia': 'Croatia',
  'Greece': 'Greece',
  'Italy': 'Italy',
  'Portugal': 'Portugal',
  'Bahamas': 'Bahamas',
  'Cayman Islands': 'Cayman Islands',
}

function getDisplayCountry(p: Provider): string {
  if (p.country === 'GB') return 'United Kingdom'
  if (p.region && REGION_TO_COUNTRY[p.region.trim()]) return REGION_TO_COUNTRY[p.region.trim()]
  if (p.country) return p.country
  if (p.region) return p.region.replace(/\n/g, ' ')
  return 'Unknown'
}

function getUKRegion(p: Provider): string {
  if (p.region) return p.region.replace(/\n/g, ' ')
  return 'Unknown'
}

interface GroupedProviders {
  uk: Record<string, Provider[]>
  international: Record<string, Provider[]>
}

function groupProviders(providers: Provider[]): GroupedProviders {
  const uk: Record<string, Provider[]> = {}
  const international: Record<string, Provider[]> = {}

  for (const p of providers) {
    if (p.not_open_to_public) continue
    if (p.country === 'GB') {
      const region = getUKRegion(p)
      ;(uk[region] ??= []).push(p)
    } else {
      const country = getDisplayCountry(p)
      ;(international[country] ??= []).push(p)
    }
  }

  // Sort groups alphabetically
  const sortObj = (obj: Record<string, Provider[]>) =>
    Object.fromEntries(Object.entries(obj).sort(([a], [b]) => a.localeCompare(b)))

  return { uk: sortObj(uk), international: sortObj(international) }
}

function buildProviderCourseMap(approvals: Approval[], courses: Course[]): Map<string, Course[]> {
  const courseById = new Map(courses.map(c => [c.id, c]))
  const map = new Map<string, Course[]>()
  for (const a of approvals) {
    if (a.status !== 'active') continue
    const course = courseById.get(a.course_id)
    if (!course) continue
    const list = map.get(a.provider_id) ?? []
    if (!list.find(c => c.id === course.id)) list.push(course)
    map.set(a.provider_id, list)
  }
  return map
}

function CourseTag({ id }: { id: string }) {
  return (
    <span style={{
      display: 'inline-block',
      fontSize: '10px',
      fontFamily: 'var(--font-data)',
      background: 'var(--soundings-bg)',
      color: 'var(--soundings)',
      border: '1px solid color-mix(in oklch, var(--soundings) 25%, transparent)',
      borderRadius: '3px',
      padding: '1px 5px',
      whiteSpace: 'nowrap',
    }}>
      {id.toUpperCase()}
    </span>
  )
}

function ProviderCard({
  provider,
  courses,
}: {
  provider: Provider
  courses: Course[]
}) {
  return (
    <div style={{
      padding: '0.65rem 0.75rem',
      borderRadius: '6px',
      border: '1px solid var(--border)',
      background: 'var(--surface)',
    }}>
      <p style={{
        margin: 0,
        fontWeight: 600,
        fontSize: '0.8rem',
        color: 'var(--ink)',
        lineHeight: 1.35,
      }}>
        {provider.website ? (
          <a
            href={provider.website}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: 'inherit', textDecoration: 'none' }}
            onMouseEnter={e => (e.currentTarget.style.textDecoration = 'underline')}
            onMouseLeave={e => (e.currentTarget.style.textDecoration = 'none')}
          >
            {provider.official_name}
          </a>
        ) : provider.official_name}
      </p>

      {(provider.region || provider.address) && (
        <p style={{ margin: '2px 0 0', fontSize: '0.7rem', color: 'var(--ink-muted)', lineHeight: 1.3 }}>
          {provider.region?.replace(/\n/g, ', ') ?? provider.address?.split('\n')[0]}
        </p>
      )}

      {courses.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '3px', marginTop: '6px' }}>
          {courses.map(c => <CourseTag key={c.id} id={c.id} />)}
        </div>
      )}

      {(provider.telephone || provider.email) && (
        <div style={{ marginTop: '5px', display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          {provider.telephone && (
            <a href={`tel:${provider.telephone}`}
              style={{ fontSize: '0.68rem', color: 'var(--ink-muted)', textDecoration: 'none' }}>
              {provider.telephone}
            </a>
          )}
          {provider.email && (
            <a href={`mailto:${provider.email}`}
              style={{ fontSize: '0.68rem', color: 'var(--ink-muted)', textDecoration: 'none' }}>
              {provider.email}
            </a>
          )}
        </div>
      )}
    </div>
  )
}

function RegionSection({
  name,
  providers,
  providerCourseMap,
}: {
  name: string
  providers: Provider[]
  providerCourseMap: Map<string, Course[]>
}) {
  const [open, setOpen] = useState(true)

  return (
    <section>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.45rem 0',
          background: 'none',
          border: 'none',
          borderBottom: '1px solid var(--border)',
          cursor: 'pointer',
          color: 'var(--ink)',
          textAlign: 'left',
        }}
      >
        <span style={{
          fontFamily: 'var(--font-ui)',
          fontWeight: 700,
          fontSize: '0.78rem',
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          color: 'var(--navy-700)',
        }}>
          {name}
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{
            fontSize: '0.68rem',
            fontFamily: 'var(--font-data)',
            color: 'var(--ink-faint)',
          }}>
            {providers.length}
          </span>
          <svg
            width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
            style={{ transition: 'transform 150ms', transform: open ? 'rotate(0deg)' : 'rotate(-90deg)', color: 'var(--ink-faint)' }}
            aria-hidden="true"
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </span>
      </button>

      {open && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: '0.5rem',
          paddingTop: '0.6rem',
          paddingBottom: '0.75rem',
        }}>
          {providers.map(p => (
            <ProviderCard
              key={p.id}
              provider={p}
              courses={providerCourseMap.get(p.id) ?? []}
            />
          ))}
        </div>
      )}
    </section>
  )
}

export function MapView() {
  const { providers, approvals, courses, loading, error } = useData()
  const [search, setSearch] = useState('')

  const providerCourseMap = useMemo(() => buildProviderCourseMap(approvals, courses), [approvals, courses])

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim()
    if (!q) return providers
    return providers.filter(p =>
      p.official_name?.toLowerCase().includes(q) ||
      p.region?.toLowerCase().includes(q) ||
      p.address?.toLowerCase().includes(q)
    )
  }, [providers, search])

  const grouped = useMemo(() => groupProviders(filtered), [filtered])

  if (loading) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: 'calc(100vh - 3.5rem)', color: 'var(--ink-muted)',
        fontFamily: 'var(--font-ui)', fontSize: '1rem',
      }}>
        Loading chart…
      </div>
    )
  }

  if (error) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: 'calc(100vh - 3.5rem)', color: 'var(--chart-red)',
        fontFamily: 'var(--font-sans)', fontSize: '0.9rem',
      }}>
        Failed to load data: {error}
      </div>
    )
  }

  const ukRegions = Object.keys(grouped.uk)
  const intlCountries = Object.keys(grouped.international)
  const totalShown = filtered.filter(p => !p.not_open_to_public).length

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      {/* Header */}
      <div style={{ marginBottom: '1.25rem' }}>
        <h1 style={{
          fontFamily: 'var(--font-ui)',
          fontWeight: 800,
          fontSize: '1.25rem',
          color: 'var(--navy-950)',
          margin: '0 0 0.25rem',
          letterSpacing: '-0.02em',
        }}>
          Training providers by location
        </h1>
        <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--ink-muted)', fontFamily: 'var(--font-sans)' }}>
          {totalShown} MCA-approved training providers worldwide
        </p>
      </div>

      {/* Search */}
      <div style={{ marginBottom: '1.25rem' }}>
        <input
          type="search"
          placeholder="Filter by name or region…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{
            width: '100%',
            maxWidth: '360px',
            padding: '0.45rem 0.75rem',
            borderRadius: '6px',
            border: '1px solid var(--border)',
            background: 'var(--surface)',
            color: 'var(--ink)',
            fontFamily: 'var(--font-sans)',
            fontSize: '0.85rem',
            outline: 'none',
          }}
          onFocus={e => (e.currentTarget.style.borderColor = 'var(--soundings)')}
          onBlur={e => (e.currentTarget.style.borderColor = 'var(--border)')}
        />
      </div>

      {/* UK sections */}
      {ukRegions.length > 0 && (
        <div style={{ marginBottom: '2rem' }}>
          <h2 style={{
            fontFamily: 'var(--font-ui)',
            fontWeight: 700,
            fontSize: '0.95rem',
            color: 'var(--navy-800)',
            margin: '0 0 0.75rem',
            letterSpacing: '-0.01em',
          }}>
            United Kingdom
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            {ukRegions.map(region => (
              <RegionSection
                key={region}
                name={region}
                providers={grouped.uk[region]}
                providerCourseMap={providerCourseMap}
              />
            ))}
          </div>
        </div>
      )}

      {/* International sections */}
      {intlCountries.length > 0 && (
        <div>
          <h2 style={{
            fontFamily: 'var(--font-ui)',
            fontWeight: 700,
            fontSize: '0.95rem',
            color: 'var(--navy-800)',
            margin: '0 0 0.75rem',
            letterSpacing: '-0.01em',
          }}>
            International
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            {intlCountries.map(country => (
              <RegionSection
                key={country}
                name={country}
                providers={grouped.international[country]}
                providerCourseMap={providerCourseMap}
              />
            ))}
          </div>
        </div>
      )}

      {totalShown === 0 && (
        <p style={{ color: 'var(--ink-muted)', fontFamily: 'var(--font-sans)', fontSize: '0.85rem' }}>
          No providers match "{search}".
        </p>
      )}
    </div>
  )
}
