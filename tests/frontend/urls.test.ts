import { describe, it, expect } from 'vitest'
import { encodeFilters, decodeFilters } from '../../src/lib/urls'
import type { FilterState } from '../../src/types/data'

describe('encodeFilters / decodeFilters round-trip', () => {
  it('round-trips a fully populated FilterState', () => {
    const filters: FilterState = {
      category: 'stcw_basic',
      country: 'GB',
      region: 'Kent',
      maxPrice: 875,
      currency: 'GBP',
      deliveryFormat: 'in_person',
      hasDates: true,
      hasPrice: false,
      provider: 'msa-dover',
      sortBy: 'earliest_date',
      query: 'personal survival',
    }
    const decoded = decodeFilters(encodeFilters(filters))
    expect(decoded).toEqual(filters)
  })

  it('round-trips an empty FilterState', () => {
    const decoded = decodeFilters(encodeFilters({}))
    expect(decoded).toEqual({})
  })

  it('round-trips maxPrice: 0', () => {
    const filters: FilterState = { maxPrice: 0 }
    const decoded = decodeFilters(encodeFilters(filters))
    expect(decoded.maxPrice).toBe(0)
  })
})
