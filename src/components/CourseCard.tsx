import { Link } from 'react-router-dom'
import type { Course } from '../types/data'

function OtherProvidersLink() {
  return (
    <Link
      to="/other-providers"
      onClick={e => e.stopPropagation()}
      style={{
        fontFamily: 'var(--font-data)',
        fontSize: '0.63rem',
        color: 'var(--soundings)',
        textDecoration: 'none',
        whiteSpace: 'nowrap',
      }}
      className="hover:underline"
      aria-label="Browse other providers"
    >
      other providers →
    </Link>
  )
}

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
        display: 'flex',
        alignItems: 'center',
        gap: '0.75rem',
        padding: '0.6rem 0.875rem',
        textDecoration: 'none',
        transition: 'border-color 120ms, background 120ms',
      }}
      className="group focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--chart-red)] hover:border-[var(--border-strong)] hover:bg-[var(--paper)]"
    >
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
        <div style={{
          fontFamily: 'var(--font-ui)',
          color: 'var(--navy-950)',
          fontSize: '0.9375rem',
          fontWeight: 700,
          lineHeight: 1.3,
        }} className="group-hover:text-[var(--chart-red)] transition-colors">
          {course.official_name}
        </div>
      </div>

      {/* Right-hand data column */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-end',
        gap: '0.15rem',
        flexShrink: 0,
      }}>
        <span style={{
          fontFamily: 'var(--font-data)',
          fontSize: '0.7rem',
          color: 'var(--ink-faint)',
        }}>
          {course.provider_count} {course.provider_count === 1 ? 'centre' : 'centres'}
        </span>
        {course.earliest_known_date ? (
          <span style={{
            fontFamily: 'var(--font-data)',
            fontSize: '0.7rem',
            color: 'var(--soundings)',
            fontWeight: 600,
          }}>
            {course.earliest_known_date}
          </span>
        ) : (
          <OtherProvidersLink />
        )}
        {course.lowest_known_price_gbp !== null && (
          <span style={{
            fontFamily: 'var(--font-data)',
            fontSize: '0.7rem',
            color: 'var(--ink-muted)',
          }}>
            £{course.lowest_known_price_gbp.toFixed(0)}+
          </span>
        )}
      </div>

      <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor"
        strokeWidth="2" strokeLinecap="round" aria-hidden="true"
        style={{ color: 'var(--ink-faint)', flexShrink: 0 }}
        className="group-hover:text-[var(--chart-red)] transition-colors">
        <path d="M6 4l4 4-4 4"/>
      </svg>
    </Link>
  )
}
