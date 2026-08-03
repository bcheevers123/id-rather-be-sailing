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
        borderRadius: '4px',
        display: 'flex',
        alignItems: 'center',
        gap: '0.75rem',
        padding: '0.65rem 0.875rem',
        textDecoration: 'none',
        transition: 'border-color 100ms, background 100ms',
      }}
      className="group focus:outline-none focus-visible:ring-1 focus-visible:ring-[var(--phosphor)] hover:border-[var(--accent)] hover:bg-[var(--surface-2)]"
    >
      {/* AIS-style side marker */}
      <div style={{
        width: '3px',
        alignSelf: 'stretch',
        borderRadius: '2px',
        background: 'var(--accent-tint)',
        borderLeft: '2px solid var(--accent)',
        flexShrink: 0,
        transition: 'border-color 100ms',
      }} className="group-hover:border-[var(--phosphor)]" aria-hidden="true" />

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 mb-0.5 flex-wrap">
          <span className="cat-chip">{catLabel}</span>
          {course.abbreviation && (
            <span style={{
              color: 'var(--ink-faint)',
              fontSize: '0.72rem',
              fontFamily: 'var(--font-data)',
              fontWeight: 600,
              letterSpacing: '0.04em',
            }}>
              {course.abbreviation}
            </span>
          )}
        </div>
        <div style={{ color: 'var(--ink)', fontSize: '0.875rem', fontWeight: 600, lineHeight: 1.3 }}
          className="group-hover:text-[var(--accent)] transition-colors">
          {course.official_name}
        </div>
      </div>

      {/* Data column — right side */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-end',
        gap: '0.2rem',
        flexShrink: 0,
      }}>
        <span style={{
          fontFamily: 'var(--font-data)',
          fontSize: '0.72rem',
          color: 'var(--ink-faint)',
          letterSpacing: '0.01em',
        }}>
          {course.provider_count} {course.provider_count === 1 ? 'centre' : 'centres'}
        </span>
        {course.earliest_known_date ? (
          <span style={{
            fontFamily: 'var(--font-data)',
            fontSize: '0.72rem',
            color: 'var(--accent)',
            fontWeight: 600,
          }}>
            {course.earliest_known_date}
          </span>
        ) : (
          <span style={{
            fontFamily: 'var(--font-data)',
            fontSize: '0.68rem',
            color: 'var(--ink-faint)',
          }}>
            no dates
          </span>
        )}
        {course.lowest_known_price_gbp !== null && (
          <span style={{
            fontFamily: 'var(--font-data)',
            fontSize: '0.72rem',
            color: 'var(--ink-muted)',
          }}>
            £{course.lowest_known_price_gbp.toFixed(0)}+
          </span>
        )}
      </div>

      {/* Chevron */}
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor"
        strokeWidth="2" strokeLinecap="round" aria-hidden="true"
        style={{ color: 'var(--ink-faint)', flexShrink: 0 }}
        className="group-hover:text-[var(--accent)] transition-colors">
        <path d="M6 4l4 4-4 4"/>
      </svg>
    </Link>
  )
}
