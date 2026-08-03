import { useMemo, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useData } from '../hooks/useData'
import { buildSearchIndex, searchCourses } from '../lib/search'
import { SearchBar } from '../components/SearchBar'
import { CourseCard } from '../components/CourseCard'
import type { CourseCategory } from '../types/data'

const CATEGORY_ORDER: CourseCategory[] = [
  'stcw_basic', 'stcw_advanced', 'stcw_refresher', 'stcw_tanker',
  'stcw_igf', 'stcw_helm', 'stcw_ecdis_naest', 'gmdss',
  'high_voltage', 'security', 'deck_yacht', 'sv_engineering',
  'engineering_other', 'polar', 'workboat', 'other',
]

const CATEGORY_LABELS: Record<CourseCategory, string> = {
  stcw_basic: 'STCW Basic Training',
  stcw_advanced: 'STCW Advanced Training',
  stcw_refresher: 'Updating STCW Training',
  stcw_tanker: 'Tanker Training',
  stcw_igf: 'IGF Code Training (Alternative Fuels)',
  stcw_helm: 'HELM — Leadership & Management',
  stcw_ecdis_naest: 'ECDIS & NAEST',
  gmdss: 'GMDSS / Radio',
  high_voltage: 'High Voltage',
  security: 'Security Training',
  deck_yacht: 'Deck Yacht Modules',
  sv_engineering: 'Small Vessel Engineering Modules',
  engineering_other: 'Non-STCW Engineering',
  polar: 'Polar Waters Training',
  workboat: 'Workboat Courses',
  other: 'Other MCA-approved Training',
}

export function Catalogue() {
  const { courses, loading, error } = useData()
  const [searchParams, setSearchParams] = useSearchParams()
  const [openCategories, setOpenCategories] = useState<Set<CourseCategory>>(new Set())
  const query = searchParams.get('q') ?? ''

  const fuse = useMemo(() => buildSearchIndex(courses), [courses])

  const searchResults = useMemo(() => {
    if (!query.trim()) return null
    return searchCourses(fuse, query)
  }, [fuse, query])

  const setQuery = useCallback((q: string) => {
    const p = new URLSearchParams(searchParams)
    if (q) p.set('q', q)
    else p.delete('q')
    setSearchParams(p, { replace: true })
  }, [searchParams, setSearchParams])

  const toggleCategory = (cat: CourseCategory) => {
    setOpenCategories(prev => {
      const next = new Set(prev)
      if (next.has(cat)) next.delete(cat)
      else next.add(cat)
      return next
    })
  }

  if (loading) return <div className="p-8 text-center text-gray-500">Loading courses…</div>
  if (error) return <div className="p-8 text-center text-red-600">Failed to load data: {error}</div>

  const coursesByCategory = new Map<CourseCategory, typeof courses>()
  for (const course of courses) {
    const arr = coursesByCategory.get(course.category) ?? []
    arr.push(course)
    coursesByCategory.set(course.category, arr)
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-2">MCA-Approved Maritime Training</h1>
      <p className="text-sm text-gray-500 mb-6">
        Browse every course found in the official MCA approved training providers list.
        Approval status is authoritative; schedule availability varies by provider.
      </p>

      <SearchBar value={query} onChange={setQuery} placeholder="Search by course name, abbreviation…" />

      {searchResults !== null ? (
        <section aria-label="Search results" className="mt-6">
          <p className="text-sm text-gray-500 mb-3">
            {searchResults.length} result{searchResults.length !== 1 ? 's' : ''} for "{query}"
          </p>
          {searchResults.length === 0 ? (
            <p className="text-gray-400">No courses match your search. Try a different term or browse by category below.</p>
          ) : (
            <div className="space-y-3">
              {searchResults.map(course => <CourseCard key={course.id} course={course} />)}
            </div>
          )}
        </section>
      ) : (
        <div className="mt-6 space-y-2">
          {CATEGORY_ORDER.map(cat => {
            const catCourses = coursesByCategory.get(cat) ?? []
            if (catCourses.length === 0) return null
            const isOpen = openCategories.has(cat)
            return (
              <div key={cat} className="rounded-lg border border-gray-200 overflow-hidden">
                <button
                  onClick={() => toggleCategory(cat)}
                  aria-expanded={isOpen}
                  className="flex w-full items-center justify-between px-4 py-3 text-left font-medium text-gray-900 bg-gray-50 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-navy-600"
                >
                  <span>{CATEGORY_LABELS[cat]}</span>
                  <span className="ml-2 text-sm text-gray-500">{catCourses.length} course{catCourses.length !== 1 ? 's' : ''}</span>
                </button>
                {isOpen && (
                  <div className="divide-y divide-gray-100 px-4 py-2 space-y-2">
                    {catCourses.map(course => <CourseCard key={course.id} course={course} />)}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </main>
  )
}
