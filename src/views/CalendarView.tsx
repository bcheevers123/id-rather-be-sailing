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
    const url = safeHref(event.resource.offering.booking_url)
    if (url) window.open(url, '_blank', 'noopener,noreferrer')
  }, [])

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8">
        <div className="skeleton" style={{ height: 36, width: 220, marginBottom: '0.5rem' }} />
        <div className="skeleton" style={{ height: 20, width: 380, marginBottom: '1.5rem' }} />
        <div className="skeleton" style={{ height: 520, borderRadius: '4px' }} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8" role="alert">
        <div style={{
          background: 'var(--danger-bg)',
          border: '1px solid oklch(40% 0.15 22 / 0.5)',
          borderRadius: '4px',
          padding: '1rem',
          color: 'var(--danger)',
          fontFamily: 'var(--font-data)',
          fontSize: '0.875rem',
        }}>
          {error}
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div style={{ marginBottom: '1.25rem' }}>
        <h1 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--ink)', letterSpacing: '-0.02em', marginBottom: '0.25rem' }}>
          Course Calendar
        </h1>
        <p style={{ fontSize: '0.8rem', color: 'var(--ink-faint)', fontFamily: 'var(--font-data)' }}>
          {events.length} upcoming {events.length === 1 ? 'session' : 'sessions'} with confirmed dates · click to book
        </p>
      </div>

      <div
        aria-label="Course calendar"
        style={{
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: '4px',
          padding: '1rem',
        }}
      >
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
          showAllEvents
          style={{ height: view === Views.AGENDA ? 600 : undefined }}
          tooltipAccessor={(e: CalEvent) => {
            const { offering, course, provider } = e.resource
            const price = offering.price
              ? ` · £${offering.price.toFixed(0)}`
              : ''
            return `${course.official_name}\n${provider.official_name}${price}`
          }}
        />
      </div>
    </div>
  )
}
