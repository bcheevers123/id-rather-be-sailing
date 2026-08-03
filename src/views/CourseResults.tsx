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
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor"
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
      <main className="mx-auto max-w-5xl px-4 py-8">
        <div style={{ height: '24px', width: '120px', borderRadius: '6px', background: 'var(--surface-3)', marginBottom: '1.5rem' }} />
        <div style={{ height: '36px', width: '60%', borderRadius: '6px', background: 'var(--surface-3)', marginBottom: '0.5rem' }} />
        <div style={{ height: '20px', width: '80%', borderRadius: '6px', background: 'var(--surface-3)' }} />
        <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }`}</style>
      </main>
    )
  }

  if (error) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-8">
        <div role="alert" style={{
          background: 'var(--danger-tint)',
          border: '1px solid oklch(80% 0.08 22)',
          borderRadius: '8px',
          padding: '1.25rem',
          color: 'oklch(35% 0.14 22)',
        }}>
          {error}
        </div>
      </main>
    )
  }

  if (!course) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-8 text-center">
        <p style={{ color: 'var(--ink-muted)', marginBottom: '0.75rem' }}>Course not found.</p>
        <Link to="/" className="flex items-center justify-center gap-1.5 text-sm">
          <BackArrow /> Back to catalogue
        </Link>
      </main>
    )
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <Link
        to="/"
        className="flex items-center gap-1.5 text-sm hover:underline mb-5"
        style={{ color: 'var(--ink-muted)', width: 'fit-content' }}
      >
        <BackArrow /> All courses
      </Link>

      <header style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
          <h1 style={{ fontSize: '1.375rem', fontWeight: 700, color: 'var(--ink)' }}>
            {course.official_name}
          </h1>
          {course.abbreviation && (
            <code style={{
              background: 'var(--surface-3)',
              color: 'var(--ink-muted)',
              borderRadius: '5px',
              padding: '0.15rem 0.5rem',
              fontSize: '0.8125rem',
              fontFamily: 'ui-monospace, monospace',
            }}>
              {course.abbreviation}
            </code>
          )}
        </div>
        {course.description && (
          <p style={{ fontSize: '0.9375rem', color: 'var(--ink-muted)', maxWidth: '65ch', lineHeight: 1.6 }}>
            {course.description}
          </p>
        )}
        <p style={{ fontSize: '0.75rem', color: 'var(--ink-faint)', marginTop: '0.5rem' }}>
          MCA source:{' '}
          <a href={safeHref(course.source_pdf_url) ?? '#'} target="_blank" rel="noopener noreferrer">
            official provider list
          </a>
          {' '}· updated {course.source_updated_date}
        </p>
      </header>

      <DisambiguationBanner note={course.confusion_note} />

      <div className="flex gap-6 flex-col md:flex-row">
        <aside className="md:w-52 flex-shrink-0">
          <FilterPanel filters={filters} onChange={setFilters} availableCountries={availableCountries} />
        </aside>

        <section aria-label="Approved training providers" className="flex-1 min-w-0">
          <p style={{ fontSize: '0.8125rem', color: 'var(--ink-muted)', marginBottom: '1rem' }}>
            <strong style={{ color: 'var(--ink)' }}>{sorted.length}</strong>
            {' '}approved {sorted.length === 1 ? 'centre' : 'centres'}
            {Object.keys(filters).length > 0 ? ' (filtered)' : ''}
          </p>
          {sorted.length === 0 ? (
            <div style={{
              background: 'var(--surface-2)',
              border: '1px solid var(--border)',
              borderRadius: '8px',
              padding: '2rem',
              textAlign: 'center',
              color: 'var(--ink-muted)',
              fontSize: '0.875rem',
            }}>
              No providers match the current filters.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {sorted.map(result => (
                <ProviderResultCard key={result.provider.id} result={result} />
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  )
}
