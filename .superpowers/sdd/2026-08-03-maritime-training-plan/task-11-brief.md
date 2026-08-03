# Task 11 Brief: Core UI components

## Context

Task 11 of the "I'd Rather Be Sailing" plan. Tasks 1–10 are complete. The Python pipeline and TypeScript data layer exist. You are now building React UI components — pure presentational pieces that the views (Task 12) will compose.

## Working directory

`C:\Users\BarryCheevers\OneDrive - Anomali\Desktop\Fun\I'd Rather Be Sailing`
Branch: `feature/maritime-training`

Frontend: Vite + React 18 + TypeScript 5 + Tailwind CSS 3. Run `npm install` if needed.

No tests required for this task — components are pure presentational. Just create the files, verify the TypeScript build compiles (`npm run build`), and commit.

## Files to create

- `src/lib/freshness.ts`
- `src/components/FreshnessBadge.tsx`
- `src/components/DisambiguationBanner.tsx`
- `src/components/SearchBar.tsx`
- `src/components/CourseCard.tsx`
- `src/components/ProviderResult.tsx`
- `src/components/FilterPanel.tsx`

## Interfaces consumed (already exist in the codebase)

From `src/types/data.ts`:
- `FreshnessStatus` — union type for 5 statuses
- `Course`, `Provider`, `Offering`, `Approval`
- `FilterState`, `DeliveryFormat`, `SortField`

From `src/lib/filters.ts`:
- `ProviderResult` — interface with `{ provider, approval, offerings, earliestDate, lowestPrice }`

React Router 6 is already installed — `Link` from `'react-router-dom'` is available.

## Implementation

### src/lib/freshness.ts

```typescript
import type { FreshnessStatus } from '../types/data'

interface FreshnessDisplay {
  label: string
  colour: string
  description: string
}

export function getFreshnessDisplay(status: FreshnessStatus): FreshnessDisplay {
  switch (status) {
    case 'verified':
      return { label: 'Verified', colour: 'bg-green-100 text-green-800', description: 'Checked within the last 24 hours' }
    case 'recently_checked':
      return { label: 'Recently checked', colour: 'bg-yellow-100 text-yellow-800', description: 'Checked within the last 7 days' }
    case 'stale':
      return { label: 'Stale', colour: 'bg-orange-100 text-orange-800', description: 'Last known data — check may have failed or be overdue' }
    case 'source_unavailable':
      return { label: 'Source unavailable', colour: 'bg-red-100 text-red-800', description: 'Provider website could not be reached — showing last known data' }
    case 'no_public_schedule':
      return { label: 'No public schedule', colour: 'bg-gray-100 text-gray-700', description: 'This provider does not publish their schedule online' }
  }
}
```

### src/components/FreshnessBadge.tsx

```typescript
import { getFreshnessDisplay } from '../lib/freshness'
import type { FreshnessStatus } from '../types/data'

interface Props {
  status: FreshnessStatus
}

export function FreshnessBadge({ status }: Props) {
  const { label, colour, description } = getFreshnessDisplay(status)
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${colour}`}
      title={description}
      aria-label={`Data status: ${label}. ${description}`}
    >
      {label}
    </span>
  )
}
```

### src/components/DisambiguationBanner.tsx

```typescript
interface Props {
  note: string
}

export function DisambiguationBanner({ note }: Props) {
  return (
    <div
      role="note"
      className="mb-4 rounded border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900"
    >
      <span className="font-semibold">Similar courses exist: </span>
      {note}
    </div>
  )
}
```

### src/components/SearchBar.tsx

```typescript
import { useId } from 'react'

interface Props {
  value: string
  onChange: (value: string) => void
  placeholder?: string
}

export function SearchBar({ value, onChange, placeholder = 'Search courses…' }: Props) {
  const id = useId()
  return (
    <div className="relative w-full">
      <label htmlFor={id} className="sr-only">Search maritime training courses</label>
      <input
        id={id}
        type="search"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 pl-10 text-base shadow-sm focus:border-navy-600 focus:outline-none focus:ring-2 focus:ring-navy-600"
        autoComplete="off"
        spellCheck={false}
      />
      <svg
        aria-hidden="true"
        className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400"
        viewBox="0 0 20 20" fill="currentColor"
      >
        <path fillRule="evenodd" d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z" clipRule="evenodd" />
      </svg>
    </div>
  )
}
```

### src/components/CourseCard.tsx

```typescript
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
```

### src/components/ProviderResult.tsx

```typescript
import { FreshnessBadge } from './FreshnessBadge'
import type { ProviderResult as ProviderResultType } from '../lib/filters'

interface Props {
  result: ProviderResultType
}

export function ProviderResultCard({ result }: Props) {
  const { provider, approval, offerings } = result
  const overallStatus = offerings[0]?.freshness_status ?? 'no_public_schedule'

  return (
    <article
      className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
      aria-label={provider.official_name}
    >
      <div className="flex items-start justify-between gap-2 flex-wrap">
        <div>
          <h3 className="text-base font-semibold text-gray-900">{provider.official_name}</h3>
          <p className="text-sm text-gray-500">
            {[provider.city, provider.region, provider.country].filter(Boolean).join(', ')}
          </p>
          {provider.address && (
            <p className="mt-0.5 text-xs text-gray-400">{provider.address}</p>
          )}
        </div>
        <FreshnessBadge status={overallStatus} />
      </div>

      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm">
        {provider.website && (
          <a href={provider.website} target="_blank" rel="noopener noreferrer"
            className="text-navy-700 underline hover:text-navy-900 focus:outline-none focus:ring-2 focus:ring-navy-600">
            Website
          </a>
        )}
        {provider.telephone && <span className="text-gray-600">{provider.telephone}</span>}
        {provider.email && (
          <a href={`mailto:${provider.email}`} className="text-navy-700 underline hover:text-navy-900">
            {provider.email}
          </a>
        )}
      </div>

      {offerings.length > 0 ? (
        <div className="mt-3">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500 mb-1">Upcoming dates</p>
          <ul className="space-y-1">
            {offerings.slice(0, 5).map(o => (
              <li key={o.id} className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-sm">
                <span className="font-medium text-gray-900">{o.start_date}–{o.end_date}</span>
                {o.price !== null ? (
                  <span className="text-gray-600">
                    {o.currency} {o.price.toFixed(2)}
                    {o.vat_included !== null && (
                      <span className="text-gray-400 text-xs"> ({o.vat_included ? 'incl. VAT' : 'excl. VAT'})</span>
                    )}
                  </span>
                ) : (
                  <span className="text-gray-400">Price not published</span>
                )}
                {o.booking_url && (
                  <a href={o.booking_url} target="_blank" rel="noopener noreferrer"
                    className="text-navy-700 underline text-xs hover:text-navy-900 focus:outline-none focus:ring-2 focus:ring-navy-600">
                    Book →
                  </a>
                )}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="mt-3 rounded bg-gray-50 px-3 py-2 text-sm text-gray-500">
          No public dates found — contact provider directly
        </div>
      )}

      <div className="mt-3 border-t border-gray-100 pt-2 text-xs text-gray-400">
        MCA approval:{' '}
        <a href={approval.source_pdf_url} target="_blank" rel="noopener noreferrer"
          className="underline hover:text-gray-600">
          Source document
        </a>
        {' '}(updated {approval.source_updated_date})
      </div>
    </article>
  )
}
```

### src/components/FilterPanel.tsx

```typescript
import type { FilterState, DeliveryFormat, SortField } from '../types/data'

interface Props {
  filters: FilterState
  onChange: (filters: FilterState) => void
  availableCountries: string[]
}

export function FilterPanel({ filters, onChange, availableCountries }: Props) {
  const set = (patch: Partial<FilterState>) => onChange({ ...filters, ...patch })

  return (
    <aside aria-label="Filter results" className="space-y-4 text-sm">
      <div>
        <label htmlFor="filter-country" className="block font-medium text-gray-700 mb-1">Country</label>
        <select
          id="filter-country"
          value={filters.country ?? ''}
          onChange={e => set({ country: e.target.value || undefined })}
          className="w-full rounded border border-gray-300 px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-navy-600"
        >
          <option value="">All countries</option>
          {availableCountries.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      <div>
        <label htmlFor="filter-format" className="block font-medium text-gray-700 mb-1">Delivery format</label>
        <select
          id="filter-format"
          value={filters.deliveryFormat ?? ''}
          onChange={e => set({ deliveryFormat: (e.target.value || undefined) as DeliveryFormat | undefined })}
          className="w-full rounded border border-gray-300 px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-navy-600"
        >
          <option value="">Any format</option>
          <option value="in_person">In person</option>
          <option value="blended">Blended</option>
          <option value="online">Online</option>
        </select>
      </div>

      <fieldset>
        <legend className="block font-medium text-gray-700 mb-1">Show only</legend>
        <label className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={!!filters.hasDates}
            onChange={e => set({ hasDates: e.target.checked || undefined })}
            className="rounded border-gray-300 focus:ring-navy-600" />
          Has upcoming dates
        </label>
        <label className="flex items-center gap-2 cursor-pointer mt-1">
          <input type="checkbox" checked={!!filters.hasPrice}
            onChange={e => set({ hasPrice: e.target.checked || undefined })}
            className="rounded border-gray-300 focus:ring-navy-600" />
          Has public price
        </label>
      </fieldset>

      <div>
        <label htmlFor="filter-sort" className="block font-medium text-gray-700 mb-1">Sort by</label>
        <select
          id="filter-sort"
          value={filters.sortBy ?? 'earliest_date'}
          onChange={e => set({ sortBy: e.target.value as SortField })}
          className="w-full rounded border border-gray-300 px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-navy-600"
        >
          <option value="earliest_date">Earliest upcoming date</option>
          <option value="lowest_price">Lowest price</option>
          <option value="provider_name">Provider name</option>
          <option value="recently_verified">Most recently verified</option>
          <option value="location">Location</option>
        </select>
      </div>

      {Object.keys(filters).filter(k => filters[k as keyof FilterState] !== undefined).length > 0 && (
        <button
          onClick={() => onChange({})}
          className="w-full rounded border border-gray-300 px-3 py-1.5 text-gray-600 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-navy-600"
        >
          Clear all filters
        </button>
      )}
    </aside>
  )
}
```

## Steps

1. Create `src/components/` directory if it doesn't exist
2. Write all 7 files exactly as above
3. Run `npm run build` — must compile with zero TypeScript errors
4. Run `npm test` — existing 20 tests must still pass
5. Commit: `git commit -m "feat: UI components — FreshnessBadge, CourseCard, ProviderResult, FilterPanel"`

**Important notes:**
- The `CourseCard` import of `FreshnessBadge` was removed from the plan — `CourseCard` doesn't use it. Don't import it there.
- Tailwind class `navy-600`, `navy-700`, `navy-900` — these are custom colours. If they cause build errors because they're not defined in `tailwind.config.js`, use `blue-600`/`blue-700`/`blue-900` instead.
- `line-clamp-2` is a Tailwind utility — available in Tailwind 3.3+. If it causes errors, replace with `overflow-hidden` (the line clamp is a cosmetic enhancement).
- No `dangerouslySetInnerHTML` anywhere. All content uses JSX — never raw HTML insertion.
- All user-visible content in the `note` prop of `DisambiguationBanner` is rendered as text children, not HTML — safe automatically.
- External links (`provider.website`, `booking_url`, `approval.source_pdf_url`) always get `rel="noopener noreferrer"`.

## Report file

Write your report to: `.superpowers/sdd/2026-08-03-maritime-training-plan/task-11-report.md`

Return: Status, commit hash, build result (zero errors), npm test summary (20 passed), concerns.
