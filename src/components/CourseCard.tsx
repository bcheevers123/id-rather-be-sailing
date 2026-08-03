import { Link } from 'react-router-dom'
import type { Course } from '../types/data'

const CATEGORY_LABELS: Record<string, string> = {
  stcw_basic: 'STCW Basic',
  stcw_advanced: 'STCW Advanced',
  stcw_refresher: 'Updating STCW',
  stcw_tanker: 'Tanker',
  stcw_igf: 'IGF / Alt Fuels',
  stcw_helm: 'HELM',
  stcw_ecdis_naest: 'ECDIS & NAEST',
  gmdss: 'GMDSS / Radio',
  high_voltage: 'High Voltage',
  security: 'Security',
  deck_yacht: 'Deck Yacht',
  sv_engineering: 'SV Engineering',
  engineering_other: 'Engineering',
  polar: 'Polar Waters',
  workboat: 'Workboat',
  other: 'Other',
}

interface Props {
  course: Course
}

export function CourseCard({ course }: Props) {
  return (
    <Link
      to={`/course/${course.id}`}
      className="block rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition hover:border-navy-600 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-navy-600"
      aria-label={`${course.official_name}${course.abbreviation ? ` (${course.abbreviation})` : ''}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
            {CATEGORY_LABELS[course.category] ?? course.category}
          </p>
          <h3 className="mt-0.5 text-base font-semibold text-gray-900 leading-snug">
            {course.official_name}
            {course.abbreviation && (
              <span className="ml-2 text-sm font-normal text-gray-500">({course.abbreviation})</span>
            )}
          </h3>
          {course.description && (
            <p className="mt-1 text-sm text-gray-600 line-clamp-2">{course.description}</p>
          )}
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-600">
        <span>{course.provider_count} approved {course.provider_count === 1 ? 'centre' : 'centres'}</span>
        {course.earliest_known_date ? (
          <span>Next: {course.earliest_known_date}</span>
        ) : (
          <span className="text-gray-400">No dates found</span>
        )}
        {course.lowest_known_price_gbp !== null ? (
          <span>From £{course.lowest_known_price_gbp.toFixed(0)}</span>
        ) : (
          <span className="text-gray-400">Price not published</span>
        )}
      </div>
    </Link>
  )
}
