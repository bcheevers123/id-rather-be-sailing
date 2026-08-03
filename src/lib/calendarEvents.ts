import type { Offering, Course, Provider } from '../types/data'

export interface CalEventResource {
  offering: Offering
  course: Course
  provider: Provider
}

export interface CalEvent {
  id: string
  title: string
  start: Date
  end: Date
  resource: CalEventResource
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
      resource: { offering, course, provider },
    })
  }

  return events
}
