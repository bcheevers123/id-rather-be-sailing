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
