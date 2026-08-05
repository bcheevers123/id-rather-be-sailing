import type { Offering, Course, Provider } from '../types/data'

export interface CalEventResource {
  offering: Offering
  offerings: Offering[]
  course: Course
  provider: Provider
}

export interface CalEvent {
  id: string
  title: string
  start: Date
  end: Date
  allDay: true
  color: string
  groupCount: number
  resource: CalEventResource
}

// Muted Admiralty palette — one distinct colour per course, easy on the eye
const COURSE_COLOURS: Record<string, string> = {
  // STCW Basic
  pst:  'oklch(44% 0.10 248)',   // deep soundings blue — survival at sea
  efa:  'oklch(44% 0.12 158)',   // teal-green — first aid / medical
  fpff: 'oklch(42% 0.11 38)',    // warm amber-brown — fire
  pssr: 'oklch(42% 0.10 290)',   // slate purple — safety/social
  // STCW Advanced
  aff:  'oklch(40% 0.13 35)',    // deep amber — advanced fire
  pscrb:'oklch(40% 0.09 220)',   // slate blue — rescue boats
  mfa:  'oklch(40% 0.11 155)',   // forest green — medical first aid
  mc:   'oklch(38% 0.10 152)',   // dark green — medical care
  frb:  'oklch(38% 0.09 212)',   // navy — fast rescue
  // Refreshers
  upst: 'oklch(46% 0.08 248)',
  ufpff:'oklch(44% 0.09 38)',
  uaff: 'oklch(42% 0.10 35)',
  upscrb:'oklch(42% 0.07 220)',
}
const CATEGORY_COLOURS: Record<string, string> = {
  stcw_basic:     'oklch(44% 0.10 248)',
  stcw_advanced:  'oklch(40% 0.11 35)',
  stcw_refresher: 'oklch(46% 0.08 248)',
  deck_yacht:     'oklch(42% 0.10 195)',
  gmdss:          'oklch(42% 0.10 270)',
  security:       'oklch(40% 0.09 300)',
  workboat:       'oklch(40% 0.08 60)',
  other:          'oklch(40% 0.06 240)',
}
const FALLBACK_COLOUR = 'oklch(40% 0.08 240)'

export function courseColour(courseId: string, category?: string): string {
  return COURSE_COLOURS[courseId]
    ?? (category ? CATEGORY_COLOURS[category] : undefined)
    ?? FALLBACK_COLOUR
}

export function toCalendarEvents(
  offerings: Offering[],
  courses: Course[],
  providers: Provider[],
): CalEvent[] {
  const courseMap = new Map(courses.map(c => [c.id, c]))
  const providerMap = new Map(providers.map(p => [p.id, p]))
  const events: CalEvent[] = []

  for (const offering of offerings) {
    if (!offering.start_date || !offering.end_date) continue
    const course = courseMap.get(offering.course_id)
    const provider = providerMap.get(offering.provider_id)
    if (!course || !provider) continue

    const label = course.abbreviation ?? course.official_name
    const location = provider.city ?? provider.region ?? provider.country ?? ''
    const title = `${label} — ${location}`

    const start = new Date(offering.start_date)
    // react-big-calendar treats end as exclusive for all-day events
    const endDate = new Date(offering.end_date)
    endDate.setDate(endDate.getDate() + 1)

    events.push({
      id: offering.id,
      title,
      start,
      end: endDate,
      allDay: true,
      color: courseColour(course.id, course.category),
      groupCount: 1,
      resource: { offering, offerings: [offering], course, provider },
    })
  }

  return events
}

export function groupCalendarEvents(events: CalEvent[]): CalEvent[] {
  const key = (e: CalEvent) =>
    `${e.resource.course.id}::${e.start.toISOString().slice(0, 10)}`

  const groups = new Map<string, CalEvent[]>()
  for (const e of events) {
    const k = key(e)
    const existing = groups.get(k)
    if (existing) existing.push(e)
    else groups.set(k, [e])
  }

  return Array.from(groups.values()).map(group => {
    if (group.length === 1) return { ...group[0], groupCount: 1 }
    const first = group[0]
    const label = first.resource.course.abbreviation ?? first.resource.course.official_name
    return {
      ...first,
      id: `group::${key(first)}`,
      title: `${label} (${group.length})`,
      groupCount: group.length,
      resource: {
        ...first.resource,
        offerings: group.map(e => e.resource.offering),
      },
    }
  })
}
