import { useMemo, useCallback } from 'react'
import { useParams, useSearchParams, Link } from 'react-router-dom'
import { useData } from '../hooks/useData'
import { filterProviders, sortProviderResults } from '../lib/filters'
import { decodeFilters, encodeFilters } from '../lib/urls'
import { ProviderResultCard } from '../components/ProviderResult'
import { FilterPanel } from '../components/FilterPanel'
import { DisambiguationBanner } from '../components/DisambiguationBanner'

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

  if (loading) return <div className="p-8 text-center text-gray-500">Loading…</div>
  if (error) return <div className="p-8 text-center text-red-600">{error}</div>
  if (!course) return (
    <div className="p-8 text-center">
      <p className="text-gray-500">Course not found.</p>
      <Link to="/" className="mt-2 inline-block text-navy-700 underline">← Back to catalogue</Link>
    </div>
  )

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <Link to="/" className="text-sm text-navy-700 underline hover:text-navy-900 mb-4 inline-block">← All courses</Link>

      <header className="mb-6">
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="text-2xl font-bold text-gray-900">{course.official_name}</h1>
          {course.abbreviation && (
            <span className="rounded bg-gray-100 px-2 py-0.5 text-sm font-mono text-gray-600">{course.abbreviation}</span>
          )}
        </div>
        {course.description && <p className="mt-2 text-gray-600">{course.description}</p>}
        <p className="mt-2 text-xs text-gray-400">
          MCA source:{' '}
          <a href={course.source_pdf_url} target="_blank" rel="noopener noreferrer" className="underline hover:text-gray-600">
            Official provider list
          </a>{' '}
          (updated {course.source_updated_date})
        </p>
      </header>

      {course.confusion_note && <DisambiguationBanner note={course.confusion_note} />}

      <div className="flex gap-6 flex-col md:flex-row">
        <aside className="md:w-56 flex-shrink-0">
          <FilterPanel filters={filters} onChange={setFilters} availableCountries={availableCountries} />
        </aside>

        <section aria-label="Approved training providers" className="flex-1 min-w-0">
          <p className="text-sm text-gray-500 mb-4">
            {sorted.length} approved {sorted.length === 1 ? 'centre' : 'centres'}
            {Object.keys(filters).length > 0 ? ' (filtered)' : ''}
          </p>
          {sorted.length === 0 ? (
            <p className="text-gray-400 text-sm">No providers match the current filters.</p>
          ) : (
            <div className="space-y-4">
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
