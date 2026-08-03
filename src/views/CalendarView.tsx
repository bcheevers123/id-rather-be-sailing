import { useMemo, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Calendar, dateFnsLocalizer, Views } from 'react-big-calendar'
import { format, parse, startOfWeek, getDay, addMonths } from 'date-fns'
import { enGB } from 'date-fns/locale'
import 'react-big-calendar/lib/css/react-big-calendar.css'
import { useData } from '../hooks/useData'
import { toCalendarEvents } from '../lib/calendarEvents'
import type { CalEvent } from '../lib/calendarEvents'
import { safeHref } from '../lib/safeHref'

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek: (date: Date) => startOfWeek(date, { locale: enGB }),
  getDay,
  locales: { 'en-GB': enGB },
})

export function CalendarView() {
  const { courses, providers, offerings, loading, error } = useData()
  const [searchParams] = useSearchParams()
  const [date, setDate] = useState(new Date())
  const [view, setView] = useState<(typeof Views)[keyof typeof Views]>(Views.MONTH)

  const filterCourse = searchParams.get('course') ?? ''
  const filterProvider = searchParams.get('provider') ?? ''

  const filteredOfferings = useMemo(() => {
    const today = new Date().toISOString().slice(0, 10)
    const maxDate = addMonths(new Date(), 6).toISOString().slice(0, 10)
    return offerings.filter(o =>
      o.start_date >= today &&
      o.start_date <= maxDate &&
      (!filterCourse || o.course_id === filterCourse) &&
      (!filterProvider || o.provider_id === filterProvider)
    )
  }, [offerings, filterCourse, filterProvider])

  const events = useMemo(
    () => toCalendarEvents(filteredOfferings, courses, providers),
    [filteredOfferings, courses, providers]
  )

  const handleSelectEvent = useCallback((event: CalEvent) => {
    const { offering } = event.resource
    const url = safeHref(offering.booking_url)
    if (url) {
      window.open(url, '_blank', 'noopener,noreferrer')
    }
  }, [])

  if (loading) return <div className="p-8 text-center text-gray-500">Loading calendar…</div>
  if (error) return <div role="alert" className="p-8 text-center text-red-600">{error}</div>

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Course Calendar</h1>
      <p className="text-sm text-gray-500 mb-4">
        Upcoming courses with known dates. Events without confirmed dates are not shown.
        Click an event to go to the booking page.
      </p>

      <div aria-label="Course calendar" className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm" style={{ height: 600 }}>
        <Calendar
          localizer={localizer}
          events={events}
          startAccessor="start"
          endAccessor="end"
          date={date}
          view={view}
          onNavigate={setDate}
          onView={setView}
          onSelectEvent={handleSelectEvent}
          views={[Views.MONTH, Views.AGENDA]}
          culture="en-GB"
          style={{ height: '100%' }}
          tooltipAccessor={(e: CalEvent) => {
            const { offering, course, provider } = e.resource
            const price = offering.price ? ` | ${offering.currency} ${offering.price.toFixed(2)}` : ''
            return `${course.official_name}\n${provider.official_name}${price}`
          }}
        />
      </div>
    </main>
  )
}
