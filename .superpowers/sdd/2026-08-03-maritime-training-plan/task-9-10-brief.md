# Tasks 9 & 10 Brief: TypeScript types, URL encoding, useData hook, search/filter logic

## Context

Tasks 9 and 10 of the "I'd Rather Be Sailing" plan. These are pure frontend TypeScript files with no live data dependency — they can be implemented together. The Python pipeline (Tasks 1–8) is complete. You are now building the React frontend data layer.

## Working directory

`C:\Users\BarryCheevers\OneDrive - Anomali\Desktop\Fun\I'd Rather Be Sailing`
Branch: `feature/maritime-training`

Frontend tools: `npm install` to install deps. `npm test` to run Vitest.

## Files to create

**Task 9:**
- `src/types/data.ts`
- `src/lib/urls.ts`
- `src/hooks/useData.ts`

**Task 10:**
- `src/lib/search.ts`
- `src/lib/filters.ts`
- `tests/frontend/search.test.ts`
- `tests/frontend/filters.test.ts`

## Task 9 implementation

### src/types/data.ts

```typescript
export type FreshnessStatus =
  | 'verified'
  | 'recently_checked'
  | 'stale'
  | 'source_unavailable'
  | 'no_public_schedule'

export type DeliveryFormat = 'in_person' | 'blended' | 'online' | 'unknown'

export type CourseCategory =
  | 'stcw_basic' | 'stcw_advanced' | 'stcw_refresher' | 'stcw_tanker'
  | 'stcw_igf' | 'stcw_helm' | 'stcw_ecdis_naest' | 'gmdss'
  | 'high_voltage' | 'security' | 'deck_yacht' | 'sv_engineering'
  | 'engineering_other' | 'polar' | 'workboat' | 'other'

export interface Course {
  id: string
  official_name: string
  abbreviation: string | null
  aliases: string[]
  category: CourseCategory
  description: string | null
  confusion_note: string | null
  source_pdf_url: string
  source_updated_date: string
  provider_count: number
  earliest_known_date: string | null
  lowest_known_price_gbp: number | null
}

export interface Provider {
  id: string
  official_name: string
  alt_names: string[]
  address: string | null
  city: string | null
  region: string | null
  country: string | null
  postcode: string | null
  lat: number | null
  lng: number | null
  website: string | null
  email: string | null
  telephone: string | null
  not_open_to_public: boolean
}

export interface Approval {
  course_id: string
  provider_id: string
  source_pdf_url: string
  source_updated_date: string
  status: 'active' | 'removed'
  first_seen: string
  last_seen: string
  not_open_to_public: boolean
}

export interface Offering {
  id: string
  course_id: string
  provider_id: string
  start_date: string
  end_date: string
  timezone: string
  duration_days: number | null
  price: number | null
  currency: string | null
  vat_included: boolean | null
  delivery_format: DeliveryFormat
  availability: string | null
  booking_url: string | null
  source_url: string
  last_verified: string
  freshness_status: FreshnessStatus
}

export interface ParseFailure {
  provider_id: string
  reason: string
}

export interface CoverageReport {
  generated_at: string
  total_courses: number
  total_providers: number
  total_approvals: number
  providers_with_dates: number
  providers_with_prices: number
  providers_requiring_manual_review: number
  providers_blocking_automated_collection: number
  providers_no_public_schedule: number
  last_successful_full_refresh: string | null
  parse_failures: ParseFailure[]
}

export interface FilterState {
  category?: CourseCategory
  country?: string
  region?: string
  maxPrice?: number
  currency?: string
  deliveryFormat?: DeliveryFormat
  hasDates?: boolean
  hasPrice?: boolean
  provider?: string
  sortBy?: SortField
  query?: string
}

export type SortField =
  | 'earliest_date'
  | 'lowest_price'
  | 'provider_name'
  | 'recently_verified'
  | 'location'
```

### src/lib/urls.ts

```typescript
import type { FilterState, CourseCategory, DeliveryFormat, SortField } from '../types/data'

export function encodeFilters(filters: FilterState): URLSearchParams {
  const params = new URLSearchParams()
  if (filters.category) params.set('category', filters.category)
  if (filters.country) params.set('country', filters.country)
  if (filters.region) params.set('region', filters.region)
  if (filters.maxPrice !== undefined) params.set('maxPrice', String(filters.maxPrice))
  if (filters.currency) params.set('currency', filters.currency)
  if (filters.deliveryFormat) params.set('format', filters.deliveryFormat)
  if (filters.hasDates !== undefined) params.set('hasDates', filters.hasDates ? '1' : '0')
  if (filters.hasPrice !== undefined) params.set('hasPrice', filters.hasPrice ? '1' : '0')
  if (filters.provider) params.set('provider', filters.provider)
  if (filters.sortBy) params.set('sortBy', filters.sortBy)
  if (filters.query) params.set('q', filters.query)
  return params
}

export function decodeFilters(params: URLSearchParams): FilterState {
  const filters: FilterState = {}
  const category = params.get('category')
  if (category) filters.category = category as CourseCategory
  const country = params.get('country')
  if (country) filters.country = country
  const region = params.get('region')
  if (region) filters.region = region
  const maxPrice = params.get('maxPrice')
  if (maxPrice) filters.maxPrice = Number(maxPrice)
  const currency = params.get('currency')
  if (currency) filters.currency = currency
  const format = params.get('format')
  if (format) filters.deliveryFormat = format as DeliveryFormat
  const hasDates = params.get('hasDates')
  if (hasDates !== null) filters.hasDates = hasDates === '1'
  const hasPrice = params.get('hasPrice')
  if (hasPrice !== null) filters.hasPrice = hasPrice === '1'
  const provider = params.get('provider')
  if (provider) filters.provider = provider
  const sortBy = params.get('sortBy')
  if (sortBy) filters.sortBy = sortBy as SortField
  const query = params.get('q')
  if (query) filters.query = query
  return filters
}
```

### src/hooks/useData.ts

```typescript
import { useState, useEffect } from 'react'
import type { Course, Provider, Approval, Offering, CoverageReport } from '../types/data'

const BASE = import.meta.env.BASE_URL

interface DataStore {
  courses: Course[]
  providers: Provider[]
  approvals: Approval[]
  offerings: Offering[]
  coverageReport: CoverageReport | null
  loading: boolean
  error: string | null
}

async function loadJson<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE}data/${path}`)
  if (!resp.ok) throw new Error(`Failed to load ${path}: ${resp.status}`)
  return resp.json() as Promise<T>
}

export function useData(): DataStore {
  const [state, setState] = useState<DataStore>({
    courses: [],
    providers: [],
    approvals: [],
    offerings: [],
    coverageReport: null,
    loading: true,
    error: null,
  })

  useEffect(() => {
    Promise.all([
      loadJson<Course[]>('courses.json'),
      loadJson<Provider[]>('providers.json'),
      loadJson<Approval[]>('approvals.json'),
      loadJson<Offering[]>('offerings.json'),
      loadJson<CoverageReport>('coverage_report.json'),
    ])
      .then(([courses, providers, approvals, offerings, coverageReport]) => {
        setState({ courses, providers, approvals, offerings, coverageReport, loading: false, error: null })
      })
      .catch((err: Error) => {
        setState(s => ({ ...s, loading: false, error: err.message }))
      })
  }, [])

  return state
}
```

**Task 9 commit:**
```bash
git add src/types/data.ts src/lib/urls.ts src/hooks/useData.ts
git commit -m "feat: TypeScript types, URL filter encoding, useData hook"
```

## Task 10 implementation

### tests/frontend/search.test.ts

```typescript
import { describe, it, expect, beforeAll } from 'vitest'
import { buildSearchIndex, searchCourses } from '../../src/lib/search'
import type { Course } from '../../src/types/data'

const mockCourses: Course[] = [
  {
    id: 'pst', official_name: 'Personal Survival Techniques', abbreviation: 'PST',
    aliases: ['Basic Safety Training PST'], category: 'stcw_basic',
    description: null, confusion_note: 'See UPST for refresher',
    source_pdf_url: 'https://example.com/pst.pdf', source_updated_date: '2026-07-16',
    provider_count: 47, earliest_known_date: null, lowest_known_price_gbp: null,
  },
  {
    id: 'upst', official_name: 'Updating Personal Survival Techniques', abbreviation: 'UPST',
    aliases: ['Refresher PST', 'Updating PST'], category: 'stcw_refresher',
    description: null, confusion_note: 'See PST for initial course',
    source_pdf_url: 'https://example.com/upst.pdf', source_updated_date: '2026-07-16',
    provider_count: 30, earliest_known_date: null, lowest_known_price_gbp: null,
  },
  {
    id: 'fpff', official_name: 'Fire Prevention and Fire Fighting', abbreviation: 'FPFF',
    aliases: [], category: 'stcw_basic',
    description: null, confusion_note: null,
    source_pdf_url: 'https://example.com/fpff.pdf', source_updated_date: '2026-07-16',
    provider_count: 40, earliest_known_date: null, lowest_known_price_gbp: null,
  },
]

let fuse: ReturnType<typeof buildSearchIndex>

beforeAll(() => {
  fuse = buildSearchIndex(mockCourses)
})

describe('searchCourses', () => {
  it('finds PST by abbreviation', () => {
    const results = searchCourses(fuse, 'PST')
    expect(results.map(c => c.id)).toContain('pst')
  })

  it('finds PST by partial name', () => {
    const results = searchCourses(fuse, 'personal survival')
    expect(results.map(c => c.id)).toContain('pst')
  })

  it('finds PST by alias', () => {
    const results = searchCourses(fuse, 'basic safety training')
    expect(results.map(c => c.id)).toContain('pst')
  })

  it('does not merge PST and UPST', () => {
    const upstResults = searchCourses(fuse, 'UPST')
    expect(upstResults.map(c => c.id)).toContain('upst')
  })

  it('finds FPFF by name', () => {
    const results = searchCourses(fuse, 'fire prevention')
    expect(results.map(c => c.id)).toContain('fpff')
  })

  it('returns empty array for unrecognised query', () => {
    const results = searchCourses(fuse, 'xyznotacourse999')
    expect(results).toHaveLength(0)
  })
})
```

### tests/frontend/filters.test.ts

```typescript
import { describe, it, expect } from 'vitest'
import { filterProviders, sortProviderResults } from '../../src/lib/filters'
import type { Provider, Approval, Offering } from '../../src/types/data'

const provider: Provider = {
  id: 'msa-dover', official_name: 'Maritime Skills Academy Dover', alt_names: [],
  address: 'Dover', city: 'Dover', region: 'Kent', country: 'GB', postcode: 'CT16 2FG',
  lat: null, lng: null, website: 'https://msa.com', email: null, telephone: null,
  not_open_to_public: false,
}

const approval: Approval = {
  course_id: 'pst', provider_id: 'msa-dover',
  source_pdf_url: 'https://example.com/pst.pdf', source_updated_date: '2026-07-16',
  status: 'active', first_seen: '2026-08-01', last_seen: '2026-08-03',
  not_open_to_public: false,
}

const offering: Offering = {
  id: 'pst-msa-dover-2026-08-10', course_id: 'pst', provider_id: 'msa-dover',
  start_date: '2026-08-10', end_date: '2026-08-14', timezone: 'Europe/London',
  duration_days: 5, price: 875, currency: 'GBP', vat_included: true,
  delivery_format: 'in_person', availability: null,
  booking_url: 'https://msa.com/book', source_url: 'https://msa.com/pst',
  last_verified: '2026-08-03T06:00:00Z', freshness_status: 'verified',
}

describe('filterProviders', () => {
  it('returns provider when no filters applied', () => {
    const results = filterProviders([provider], [approval], [offering], 'pst', {})
    expect(results).toHaveLength(1)
  })

  it('filters by country GB', () => {
    const results = filterProviders([provider], [approval], [offering], 'pst', { country: 'GB' })
    expect(results).toHaveLength(1)
  })

  it('excludes provider from different country', () => {
    const results = filterProviders([provider], [approval], [offering], 'pst', { country: 'FR' })
    expect(results).toHaveLength(0)
  })

  it('filters by hasDates=true', () => {
    const results = filterProviders([provider], [approval], [offering], 'pst', { hasDates: true })
    expect(results).toHaveLength(1)
  })

  it('filters by maxPrice', () => {
    const results = filterProviders([provider], [approval], [offering], 'pst', { maxPrice: 800 })
    expect(results).toHaveLength(0)
  })

  it('includes provider even when no offerings', () => {
    const results = filterProviders([provider], [approval], [], 'pst', {})
    expect(results).toHaveLength(1)
    expect(results[0].offerings).toHaveLength(0)
  })
})

describe('sortProviderResults', () => {
  it('sorts by earliest date ascending', () => {
    const p2: Provider = { ...provider, id: 'other', city: 'London', region: 'Greater London' }
    const a2: Approval = { ...approval, provider_id: 'other' }
    const o2: Offering = { ...offering, id: 'pst-other-2026-09-01', provider_id: 'other', start_date: '2026-09-01', end_date: '2026-09-05' }
    const results = filterProviders([provider, p2], [approval, a2], [offering, o2], 'pst', {})
    const sorted = sortProviderResults(results, 'earliest_date')
    expect(sorted[0].provider.id).toBe('msa-dover')
  })
})
```

### src/lib/search.ts

```typescript
import Fuse from 'fuse.js'
import type { Course } from '../types/data'

export function buildSearchIndex(courses: Course[]): Fuse<Course> {
  return new Fuse(courses, {
    threshold: 0.3,
    includeScore: true,
    keys: [
      { name: 'official_name', weight: 2 },
      { name: 'abbreviation', weight: 2 },
      { name: 'aliases', weight: 1.5 },
      { name: 'description', weight: 0.5 },
    ],
  })
}

export function searchCourses(fuse: Fuse<Course>, query: string): Course[] {
  if (!query.trim()) return []
  return fuse.search(query).map(r => r.item)
}
```

### src/lib/filters.ts

```typescript
import type { Provider, Approval, Offering, FilterState, SortField } from '../types/data'

export interface ProviderResult {
  provider: Provider
  approval: Approval
  offerings: Offering[]
  earliestDate: string | null
  lowestPrice: number | null
}

export function filterProviders(
  providers: Provider[],
  approvals: Approval[],
  offerings: Offering[],
  courseId: string,
  filters: FilterState,
): ProviderResult[] {
  const courseApprovals = approvals.filter(
    a => a.course_id === courseId && a.status === 'active'
  )
  const offeringsByProvider = new Map<string, Offering[]>()
  for (const o of offerings) {
    if (o.course_id !== courseId) continue
    const arr = offeringsByProvider.get(o.provider_id) ?? []
    arr.push(o)
    offeringsByProvider.set(o.provider_id, arr)
  }

  const providerMap = new Map(providers.map(p => [p.id, p]))
  const results: ProviderResult[] = []

  for (const approval of courseApprovals) {
    const provider = providerMap.get(approval.provider_id)
    if (!provider) continue

    const providerOfferings = offeringsByProvider.get(provider.id) ?? []
    const today = new Date().toISOString().slice(0, 10)
    const futureOfferings = providerOfferings.filter(o => o.start_date >= today)

    if (filters.country && provider.country !== filters.country) continue
    if (filters.region && provider.region !== filters.region) continue
    if (filters.provider && provider.id !== filters.provider) continue
    if (filters.deliveryFormat && !futureOfferings.some(o => o.delivery_format === filters.deliveryFormat)) continue
    if (filters.hasDates && futureOfferings.length === 0) continue
    if (filters.hasPrice && !futureOfferings.some(o => o.price !== null)) continue
    if (filters.maxPrice !== undefined) {
      const gbpOfferings = futureOfferings.filter(o => o.currency === 'GBP' && o.price !== null)
      if (gbpOfferings.length > 0 && Math.min(...gbpOfferings.map(o => o.price!)) > filters.maxPrice) continue
    }

    const sortedOfferings = [...futureOfferings].sort((a, b) => a.start_date.localeCompare(b.start_date))
    const earliestDate = sortedOfferings[0]?.start_date ?? null
    const gbpPrices = sortedOfferings.filter(o => o.currency === 'GBP' && o.price !== null).map(o => o.price!)
    const lowestPrice = gbpPrices.length > 0 ? Math.min(...gbpPrices) : null

    results.push({ provider, approval, offerings: sortedOfferings, earliestDate, lowestPrice })
  }

  return results
}

export function sortProviderResults(results: ProviderResult[], sortBy: SortField): ProviderResult[] {
  const sorted = [...results]
  switch (sortBy) {
    case 'earliest_date':
      return sorted.sort((a, b) => {
        if (!a.earliestDate && !b.earliestDate) return 0
        if (!a.earliestDate) return 1
        if (!b.earliestDate) return -1
        return a.earliestDate.localeCompare(b.earliestDate)
      })
    case 'lowest_price':
      return sorted.sort((a, b) => {
        if (a.lowestPrice === null && b.lowestPrice === null) return 0
        if (a.lowestPrice === null) return 1
        if (b.lowestPrice === null) return -1
        return a.lowestPrice - b.lowestPrice
      })
    case 'provider_name':
      return sorted.sort((a, b) => a.provider.official_name.localeCompare(b.provider.official_name))
    case 'recently_verified': {
      const statusOrder: Record<string, number> = { verified: 0, recently_checked: 1, stale: 2, source_unavailable: 3, no_public_schedule: 4 }
      return sorted.sort((a, b) => {
        const aStatus = a.offerings[0]?.freshness_status ?? 'no_public_schedule'
        const bStatus = b.offerings[0]?.freshness_status ?? 'no_public_schedule'
        return (statusOrder[aStatus] ?? 5) - (statusOrder[bStatus] ?? 5)
      })
    }
    case 'location':
      return sorted.sort((a, b) => (a.provider.city ?? '').localeCompare(b.provider.city ?? ''))
    default:
      return sorted
  }
}
```

## Steps

1. Create `src/types/` and `src/lib/` and `src/hooks/` directories as needed
2. Write all Task 9 files (`src/types/data.ts`, `src/lib/urls.ts`, `src/hooks/useData.ts`)
3. Commit Task 9: `git commit -m "feat: TypeScript types, URL filter encoding, useData hook"`
4. Write Task 10 test files first (red phase): `npm test` — expect failures
5. Write `src/lib/search.ts` and `src/lib/filters.ts`
6. Run `npm test` — all tests must pass
7. Commit Task 10: `git commit -m "feat: search index, filter/sort logic with tests"`

**Important notes:**
- `npm install` may be needed if node_modules doesn't exist
- `fuse.js` is already in `package.json` dependencies — just import it
- The `offering.start_date` comparison uses ISO date string comparison (lexicographic) which works correctly for `YYYY-MM-DD` format
- The `filterProviders` function keeps providers even when they have no offerings (just `offerings: []`)
- Tests are in `tests/frontend/` not `src/`

## Report file

Write your report to: `.superpowers/sdd/2026-08-03-maritime-training-plan/task-9-10-report.md`

Return: Status, commits (2 separate), test summary (npm test N passed), concerns.
