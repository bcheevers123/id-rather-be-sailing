import { describe, it, expect } from 'vitest'
import { toCalendarEvents } from '../../src/lib/calendarEvents'
import type { Offering, Course, Provider } from '../../src/types/data'

const offering: Offering = {
  id: 'pst-msa-2026-08-10', course_id: 'pst', provider_id: 'msa-dover',
  start_date: '2026-08-10', end_date: '2026-08-14', timezone: 'Europe/London',
  duration_days: 5, price: 875, currency: 'GBP', vat_included: true,
  delivery_format: 'in_person', availability: null,
  booking_url: 'https://msa.com/book', source_url: 'https://msa.com/pst',
  last_verified: '2026-08-03T06:00:00Z', freshness_status: 'verified',
}
const course: Course = {
  id: 'pst', official_name: 'Personal Survival Techniques', abbreviation: 'PST',
  aliases: [], category: 'stcw_basic', description: null, confusion_note: null,
  source_pdf_url: 'https://example.com/pst.pdf', source_updated_date: '2026-07-16',
  provider_count: 1, earliest_known_date: '2026-08-10', lowest_known_price_gbp: 875,
}
const provider: Provider = {
  id: 'msa-dover', official_name: 'MSA Dover', alt_names: [],
  address: null, city: 'Dover', region: 'Kent', country: 'GB', postcode: null,
  lat: null, lng: null, website: null, email: null, telephone: null,
  not_open_to_public: false,
}

describe('toCalendarEvents', () => {
  it('converts offering to calendar event', () => {
    const events = toCalendarEvents([offering], [course], [provider])
    expect(events).toHaveLength(1)
    expect(events[0].title).toContain('PST')
    expect(events[0].title).toContain('Dover')
  })

  it('sets correct start and end dates', () => {
    const events = toCalendarEvents([offering], [course], [provider])
    expect(events[0].start).toEqual(new Date('2026-08-10'))
    expect(events[0].end).toEqual(new Date('2026-08-15')) // react-big-calendar end is exclusive
  })

  it('excludes offerings without dates', () => {
    const noDate = { ...offering, start_date: '', end_date: '' }
    const events = toCalendarEvents([noDate], [course], [provider])
    expect(events).toHaveLength(0)
  })
})
