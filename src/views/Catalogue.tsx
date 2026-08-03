import { useMemo, useState, useCallback, useRef, useEffect } from 'react'
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
  stcw_basic:       'STCW Basic Safety Training',
  stcw_advanced:    'STCW Advanced Training',
  stcw_refresher:   'Updating STCW Training',
  stcw_tanker:      'Tanker Training',
  stcw_igf:         'IGF Code (Alternative Fuels)',
  stcw_helm:        'HELM — Leadership & Management',
  stcw_ecdis_naest: 'ECDIS & NAEST',
  gmdss:            'GMDSS / Radio',
  high_voltage:     'High Voltage',
  security:         'Security Training',
  deck_yacht:       'Deck Yacht Modules',
  sv_engineering:   'Small Vessel Engineering',
  engineering_other:'Non-STCW Engineering',
  polar:            'Polar Waters',
  workboat:         'Workboat',
  other:            'Other MCA-approved',
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" aria-hidden="true"
      style={{ transform: open ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 180ms cubic-bezier(0.4,0,0.2,1)', flexShrink: 0 }}
    >
      <path d="M3 6l5 5 5-5"/>
    </svg>
  )
}

function AccordionSection({
  cat, courses, isOpen, onToggle,
}: {
  cat: CourseCategory
  courses: any[]
  isOpen: boolean
  onToggle: () => void
}) {
  const bodyRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = bodyRef.current
    if (!el) return
    if (isOpen) {
      el.style.height = el.scrollHeight + 'px'
      const t = setTimeout(() => { el.style.height = 'auto' }, 200)
      return () => clearTimeout(t)
    } else {
      el.style.height = el.scrollHeight + 'px'
      requestAnimationFrame(() => {
        requestAnimationFrame(() => { el.style.height = '0' })
      })
    }
  }, [isOpen])

  return (
    <div style={{
      border: '1px solid var(--border)',
      borderRadius: '8px',
      overflow: 'hidden',
      background: 'var(--surface)',
    }}>
      <button
        onClick={onToggle}
        aria-expanded={isOpen}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.75rem 1rem',
          background: isOpen ? 'var(--surface-2)' : 'var(--surface)',
          textAlign: 'left',
          cursor: 'pointer',
          border: 'none',
          transition: 'background 120ms',
          gap: '0.5rem',
        }}
        className="hover:bg-[var(--surface-2)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-inset"
      >
        <span style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--ink)' }}>
          {CATEGORY_LABELS[cat]}
        </span>
        <div className="flex items-center gap-2 shrink-0">
          <span style={{
            fontSize: '0.75rem',
            fontWeight: 500,
            color: 'var(--ink-muted)',
            background: 'var(--surface-3)',
            borderRadius: '999px',
            padding: '0.1rem 0.55rem',
          }}>
            {courses.length}
          </span>
          <ChevronIcon open={isOpen} />
        </div>
      </button>
      <div
        ref={bodyRef}
        style={{ height: 0, overflow: 'hidden', transition: 'height 180ms cubic-bezier(0.4,0,0.2,1)' }}
      >
        <div style={{ borderTop: '1px solid var(--border)', padding: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {courses.map(course => <CourseCard key={course.id} course={course} />)}
        </div>
      </div>
    </div>
  )
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

  const coursesByCategory = useMemo(() => {
    const map = new Map<CourseCategory, typeof courses>()
    for (const course of courses) {
      const arr = map.get(course.category) ?? []
      arr.push(course)
      map.set(course.category, arr)
    }
    return map
  }, [courses])

  if (loading) {
    return (
      <main className="mx-auto max-w-4xl px-4 py-12">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} style={{
              height: '52px',
              borderRadius: '8px',
              background: 'var(--surface-3)',
              animation: 'pulse 1.5s ease-in-out infinite',
              animationDelay: `${i * 80}ms`,
            }} />
          ))}
        </div>
        <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }`}</style>
      </main>
    )
  }

  if (error) {
    return (
      <main className="mx-auto max-w-4xl px-4 py-12 text-center">
        <div role="alert" style={{
          background: 'var(--danger-tint)',
          border: '1px solid oklch(80% 0.08 22)',
          borderRadius: '8px',
          padding: '1.25rem',
          color: 'oklch(35% 0.14 22)',
        }}>
          <p style={{ fontWeight: 600, marginBottom: '0.25rem' }}>Failed to load data</p>
          <p style={{ fontSize: '0.875rem' }}>{error}</p>
        </div>
      </main>
    )
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      {/* Page header */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '1.375rem', fontWeight: 700, color: 'var(--ink)', marginBottom: '0.375rem' }}>
          MCA-Approved Maritime Training
        </h1>
        <p style={{ fontSize: '0.875rem', color: 'var(--ink-muted)', maxWidth: '60ch' }}>
          Every course in the official MCA approved training providers list.
          Approval status is authoritative; schedule availability varies by provider.
        </p>
      </div>

      <SearchBar value={query} onChange={setQuery} placeholder="Search by course name or abbreviation…" />

      {searchResults !== null ? (
        <section aria-label="Search results" style={{ marginTop: '1.5rem' }}>
          <p style={{ fontSize: '0.8125rem', color: 'var(--ink-muted)', marginBottom: '0.75rem' }}>
            {searchResults.length === 0
              ? `No results for "${query}"`
              : `${searchResults.length} result${searchResults.length !== 1 ? 's' : ''} for "${query}"`
            }
          </p>
          {searchResults.length === 0 ? (
            <p style={{ fontSize: '0.875rem', color: 'var(--ink-faint)' }}>
              Try a different term or browse by category below.
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {searchResults.map(course => <CourseCard key={course.id} course={course} />)}
            </div>
          )}
        </section>
      ) : (
        <div style={{ marginTop: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {CATEGORY_ORDER.map(cat => {
            const catCourses = coursesByCategory.get(cat) ?? []
            if (catCourses.length === 0) return null
            return (
              <AccordionSection
                key={cat}
                cat={cat}
                courses={catCourses}
                isOpen={openCategories.has(cat)}
                onToggle={() => toggleCategory(cat)}
              />
            )
          })}
        </div>
      )}
    </main>
  )
}
