import { useMemo, useCallback } from 'react'
import { useParams, useSearchParams, Link } from 'react-router-dom'
import { useData } from '../hooks/useData'
import { filterProviders, sortProviderResults } from '../lib/filters'
import { decodeFilters, encodeFilters } from '../lib/urls'
import { ProviderResultCard } from '../components/ProviderResult'
import { FilterPanel } from '../components/FilterPanel'
import { DisambiguationBanner } from '../components/DisambiguationBanner'
import { safeHref } from '../lib/safeHref'

function BackArrow() {
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M10 3L5 8l5 5"/>
    </svg>
  )
}

export function CourseResults() {
  const { id } = useParams<{ id: string }>()
  const { courses, providers, approvals, offerings, loading, error } = useData()
  const [searchParams, setSearchParams] = useSearchParams()
  const filters = useMemo(() => decodeFilters(searchParams), [searchParams])

  const course = useMemo(() => courses.find(c => c.id === id), [courses, id])

  const providerResults = useMemo(() => {
    if (!id) return []
    return filterProviders(providers, approvals, offerings, id, filters)
  }, [providers, approvals, offerings, id, filters])

  const sorted = useMemo(
    () => sortProviderResults(providerResults, filters.sortBy ?? 'earliest_date'),
    [providerResults, filters.sortBy]
  )

  const availableCountries = useMemo(() => {
    const countries = new Set(providers.map(p => p.country).filter(Boolean) as string[])
    return Array.from(countries).sort()
  }, [providers])

  const setFilters = useCallback((newFilters: typeof filters) => {
    setSearchParams(encodeFilters(newFilters), { replace: true })
  }, [setSearchParams])

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-8">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {[120, 240, 180].map((w, i) => (
            <div key={i} className="skeleton" style={{ height: i === 1 ? 36 : 20, width: w }} />
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

  if (!course) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-8 text-center">
        <p style={{ color: 'var(--ink-muted)', marginBottom: '0.75rem', fontSize: '0.875rem' }}>Course not found.</p>
        <Link to="/" className="inline-flex items-center gap-1.5 text-sm">
          <BackArrow /> Back to catalogue
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <Link
        to="/"
        className="inline-flex items-center gap-1.5 hover:underline mb-5"
        style={{ color: 'var(--ink-faint)', fontSize: '0.78rem', fontFamily: 'var(--font-data)', letterSpacing: '0.01em', textDecoration: 'none' }}
      >
        <BackArrow />
        ALL COURSES
      </Link>

      <header style={{ marginBottom: '1.5rem', marginTop: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.375rem' }}>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--ink)', letterSpacing: '-0.02em' }}>
            {course.official_name}
          </h1>
          {course.abbreviation && (
            <code style={{
              background: 'var(--accent-tint)',
              color: 'var(--accent)',
              border: '1px solid oklch(40% 0.14 155 / 0.4)',
              borderRadius: '3px',
              padding: '0.1rem 0.45rem',
              fontSize: '0.75rem',
              fontFamily: 'var(--font-data)',
              fontWeight: 700,
              letterSpacing: '0.04em',
            }}>
              {course.abbreviation}
            </code>
          )}
        </div>
        {course.description && (
          <p style={{ fontSize: '0.875rem', color: 'var(--ink-muted)', maxWidth: '65ch', lineHeight: 1.6 }}>
            {course.description}
          </p>
        )}
        <p style={{ fontSize: '0.7rem', color: 'var(--ink-faint)', marginTop: '0.5rem', fontFamily: 'var(--font-data)' }}>
          MCA source:{' '}
          <a href={safeHref(course.source_pdf_url) ?? '#'} target="_blank" rel="noopener noreferrer"
            style={{ color: 'var(--ink-faint)' }} className="hover:text-[var(--ink-muted)] hover:underline">
            gov.uk official list
          </a>
          {' '}· updated {course.source_updated_date}
        </p>
      </header>

      <DisambiguationBanner note={course.confusion_note} />

      <div className="flex gap-6 flex-col md:flex-row">
        <aside className="md:w-48 flex-shrink-0">
          <FilterPanel filters={filters} onChange={setFilters} availableCountries={availableCountries} />
        </aside>

        <section aria-label="Approved training providers" className="flex-1 min-w-0">
          <p style={{ fontSize: '0.75rem', color: 'var(--ink-faint)', marginBottom: '0.875rem', fontFamily: 'var(--font-data)' }}>
            <strong style={{ color: 'var(--ink-muted)' }}>{sorted.length}</strong>
            {' '}approved {sorted.length === 1 ? 'centre' : 'centres'}
            {Object.keys(filters).length > 0 ? ' (filtered)' : ''}
          </p>
          {sorted.length === 0 ? (
            <div style={{
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: '4px',
              padding: '2rem',
              textAlign: 'center',
              color: 'var(--ink-faint)',
              fontSize: '0.875rem',
              fontFamily: 'var(--font-data)',
            }}>
              No providers match the current filters.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {sorted.map(result => (
                <ProviderResultCard key={result.provider.id} result={result} />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
