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

  it('sorts by lowest price ascending', () => {
    const p2: Provider = { ...provider, id: 'other', official_name: 'Expensive Academy' }
    const a2: Approval = { ...approval, provider_id: 'other' }
    const o2: Offering = { ...offering, id: 'pst-other-2026-08-10', provider_id: 'other', price: 500 }
    const results = filterProviders([provider, p2], [approval, a2], [offering, o2], 'pst', {})
    const sorted = sortProviderResults(results, 'lowest_price')
    expect(sorted[0].provider.id).toBe('other')
  })

  it('sorts by provider name alphabetically', () => {
    const p2: Provider = { ...provider, id: 'other', official_name: 'Alpha Academy' }
    const a2: Approval = { ...approval, provider_id: 'other' }
    const o2: Offering = { ...offering, id: 'pst-other-2026-08-10', provider_id: 'other' }
    const results = filterProviders([provider, p2], [approval, a2], [offering, o2], 'pst', {})
    const sorted = sortProviderResults(results, 'provider_name')
    expect(sorted[0].provider.id).toBe('other')
  })

  it('sorts by recently verified (best freshness status first)', () => {
    const p2: Provider = { ...provider, id: 'other' }
    const a2: Approval = { ...approval, provider_id: 'other' }
    const o2: Offering = { ...offering, id: 'pst-other-2026-08-10', provider_id: 'other', freshness_status: 'stale' }
    const results = filterProviders([provider, p2], [approval, a2], [offering, o2], 'pst', {})
    const sorted = sortProviderResults(results, 'recently_verified')
    expect(sorted[0].provider.id).toBe('msa-dover')
  })

  it('sorts by location (city name alphabetically)', () => {
    const p2: Provider = { ...provider, id: 'other', city: 'Aberdeen' }
    const a2: Approval = { ...approval, provider_id: 'other' }
    const o2: Offering = { ...offering, id: 'pst-other-2026-08-10', provider_id: 'other' }
    const results = filterProviders([provider, p2], [approval, a2], [offering, o2], 'pst', {})
    const sorted = sortProviderResults(results, 'location')
    expect(sorted[0].provider.id).toBe('other')
  })
})
