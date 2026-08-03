import { Link } from 'react-router-dom'
import type { Course } from '../types/data'

const CATEGORY_LABELS: Record<string, string> = {
  stcw_basic:       'STCW Basic',
  stcw_advanced:    'STCW Advanced',
  stcw_refresher:   'Updating STCW',
  stcw_tanker:      'Tanker',
  stcw_igf:         'IGF / Alt Fuels',
  stcw_helm:        'HELM',
  stcw_ecdis_naest: 'ECDIS & NAEST',
  gmdss:            'GMDSS / Radio',
  high_voltage:     'High Voltage',
  security:         'Security',
  deck_yacht:       'Deck Yacht',
  sv_engineering:   'SV Engineering',
  engineering_other:'Engineering',
  polar:            'Polar Waters',
  workboat:         'Workboat',
  other:            'Other',
}

function CalendarIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor"
      strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
      <rect x="1" y="3" width="14" height="12" rx="2"/>
      <line x1="1" y1="7" x2="15" y2="7"/>
      <line x1="5" y1="1" x2="5" y2="5"/>
      <line x1="11" y1="1" x2="11" y2="5"/>
    </svg>
  )
}

function PriceIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor"
      strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
      <circle cx="8" cy="8" r="7"/>
      <path d="M8 4v8M6 6h3a1.5 1.5 0 010 3H6"/>
    </svg>
  )
}

interface Props { course: Course }

export function CourseCard({ course }: Props) {
  const catLabel = CATEGORY_LABELS[course.category] ?? course.category
  return (
    <Link
      to={`/course/${course.id}`}
      aria-label={`${course.official_name}${course.abbreviation ? ` (${course.abbreviation})` : ''}`}
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: '8px',
        display: 'block',
        transition: 'border-color 120ms, box-shadow 120ms',
      }}
      className="group p-4 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] hover:border-[var(--accent)] hover:shadow-sm"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="cat-chip">{catLabel}</span>
            {course.abbreviation && (
              <span style={{ color: 'var(--ink-muted)', fontSize: '0.8rem', fontFamily: 'ui-monospace, monospace' }}>
                {course.abbreviation}
              </span>
            )}
          </div>
          <h3 style={{ color: 'var(--ink)', fontSize: '0.9375rem', fontWeight: 600, lineHeight: 1.3 }}
            className="leading-snug group-hover:text-[var(--accent)] transition-colors">
            {course.official_name}
          </h3>
          {course.description && (
            <p style={{ color: 'var(--ink-muted)', fontSize: '0.8125rem', marginTop: '0.25rem' }}
              className="line-clamp-2">
              {course.description}
            </p>
          )}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1" style={{ fontSize: '0.8125rem', color: 'var(--ink-muted)' }}>
        <span>
          <strong style={{ color: 'var(--ink)', fontWeight: 600 }}>{course.provider_count}</strong>
          {' '}approved {course.provider_count === 1 ? 'centre' : 'centres'}
        </span>
        <span className="flex items-center gap-1">
          <CalendarIcon />
          {course.earliest_known_date
            ? <span style={{ color: 'var(--ink)' }}>From {course.earliest_known_date}</span>
            : <span style={{ color: 'var(--ink-faint)' }}>No dates listed</span>
          }
        </span>
        <span className="flex items-center gap-1">
          <PriceIcon />
          {course.lowest_known_price_gbp !== null
            ? <span style={{ color: 'var(--ink)' }}>From £{course.lowest_known_price_gbp.toFixed(0)}</span>
            : <span style={{ color: 'var(--ink-faint)' }}>Price not published</span>
          }
        </span>
      </div>
    </Link>
  )
}
