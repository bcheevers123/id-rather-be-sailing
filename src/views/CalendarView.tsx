import { useMemo, useState, useCallback } from 'react'
import React from 'react'
import type { EventProps } from 'react-big-calendar'
import { useSearchParams } from 'react-router-dom'
import { Calendar, dateFnsLocalizer, Views } from 'react-big-calendar'
import { format, parse, startOfWeek, getDay, addMonths } from 'date-fns'
import { enGB } from 'date-fns/locale'
import 'react-big-calendar/lib/css/react-big-calendar.css'
import { useData } from '../hooks/useData'
import { toCalendarEvents, courseColour, sortCalendarEvents } from '../lib/calendarEvents'
import type { CalEvent } from '../lib/calendarEvents'
import type { Provider } from '../types/data'
import { safeHref } from '../lib/safeHref'

function locationLabel(p: Provider): string {
  if (p.country === 'GB') return p.region?.replace(/\n/g, ', ') ?? 'United Kingdom'
  if (p.region) return p.region.replace(/\n/g, ' ')
  if (p.country) return p.country
  return 'Unknown'
}

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek: (date: Date) => startOfWeek(date, { locale: enGB }),
  getDay,
  locales: { 'en-GB': enGB },
})

function eventStyleGetter(event: CalEvent) {
  return {
    style: { '--rbc-event-bg': event.color } as React.CSSProperties,
  }
}

// Custom agenda event: coloured pill matching the month-view style
function AgendaEvent({ event }: EventProps<CalEvent>) {
  return (
    <span style={{
      display: 'inline-block',
      background: event.color,
      color: '#fff',
      borderRadius: 2,
      padding: '1px 8px',
      fontFamily: 'var(--font-data)',
      fontSize: '0.75rem',
      fontWeight: 600,
    }}>
      {event.title}
    </span>
  )
}

export function CalendarView() {
  const { courses, providers, offerings, loading, error } = useData()
  const [searchParams] = useSearchParams()
  const [date, setDate] = useState(new Date())
  const [view, setView] = useState<(typeof Views)[keyof typeof Views]>(Views.MONTH)
  const [filterOpen, setFilterOpen] = useState(false)
  const [hiddenCourses, setHiddenCourses] = useState<Set<string>>(new Set())
  const [hiddenLocations, setHiddenLocations] = useState<Set<string>>(new Set())
  const [calendarHeight, setCalendarHeight] = useState(700)

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
    () => sortCalendarEvents(toCalendarEvents(filteredOfferings, courses, providers)),
    [filteredOfferings, courses, providers]
  )

  const filterableCourses = useMemo(() => {
    const seen = new Map<string, { id: string; name: string; color: string }>()
    for (const e of events) {
      const c = e.resource.course
      if (!seen.has(c.id)) {
        seen.set(c.id, {
          id: c.id,
          name: c.abbreviation ?? c.official_name,
          color: courseColour(c.id, c.category),
        })
      }
    }
    return Array.from(seen.values()).sort((a, b) => a.name.localeCompare(b.name))
  }, [events])

  const filterableLocations = useMemo(() => {
    const seen = new Set<string>()
    for (const e of events) seen.add(locationLabel(e.resource.provider))
    return Array.from(seen).sort((a, b) => a.localeCompare(b))
  }, [events])

  const visibleEvents = useMemo(
    () => events.filter(e =>
      !hiddenCourses.has(e.resource.course.id) &&
      !hiddenLocations.has(locationLabel(e.resource.provider))
    ),
    [events, hiddenCourses, hiddenLocations]
  )

  // Unique courses present in the visible events — for the legend
  const legendCourses = useMemo(() => {
    const seen = new Map<string, { name: string; color: string }>()
    for (const e of visibleEvents) {
      const c = e.resource.course
      if (!seen.has(c.id)) {
        seen.set(c.id, {
          name: c.abbreviation ?? c.official_name,
          color: courseColour(c.id, c.category),
        })
      }
    }
    return Array.from(seen.values())
  }, [events])

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
          {visibleEvents.length} upcoming {visibleEvents.length === 1 ? 'session' : 'sessions'} with confirmed dates · click to book
        </p>
      </div>

      {/* Colour legend */}
      {legendCourses.length > 0 && (
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '0.5rem 1rem',
          marginBottom: '0.875rem',
        }}>
          {legendCourses.map(({ name, color }) => (
            <span key={name} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <span style={{
                display: 'inline-block',
                width: 10,
                height: 10,
                borderRadius: 2,
                background: color,
                flexShrink: 0,
              }} />
              <span style={{ fontFamily: 'var(--font-data)', fontSize: '0.68rem', color: 'var(--ink-muted)', letterSpacing: '0.03em' }}>
                {name}
              </span>
            </span>
          ))}
        </div>
      )}

      {/* Filter + height controls toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
        <button
          onClick={() => setFilterOpen(o => !o)}
          style={{
            background: 'none',
            border: '1px solid var(--border)',
            borderRadius: '4px',
            padding: '0.3rem 0.75rem',
            cursor: 'pointer',
            fontFamily: 'var(--font-data)',
            fontSize: '0.75rem',
            color: (hiddenCourses.size > 0 || hiddenLocations.size > 0) ? 'var(--chart-red)' : 'var(--ink-muted)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
          }}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
            <line x1="4" y1="6" x2="20" y2="6"/><line x1="8" y1="12" x2="16" y2="12"/><line x1="11" y1="18" x2="13" y2="18"/>
          </svg>
          {(hiddenCourses.size + hiddenLocations.size) > 0
            ? `Filters (${hiddenCourses.size + hiddenLocations.size} hidden)`
            : 'Filter'}
        </button>

        {/* Calendar height control */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <span style={{ fontFamily: 'var(--font-data)', fontSize: '0.72rem', color: 'var(--ink-faint)' }}>Row height</span>
          <button
            onClick={() => setCalendarHeight(h => Math.max(400, h - 100))}
            style={{ background: 'none', border: '1px solid var(--border)', borderRadius: '3px', width: 22, height: 22, cursor: 'pointer', color: 'var(--ink-muted)', fontSize: '0.85rem', lineHeight: 1, padding: 0 }}
            aria-label="Decrease calendar height"
          >−</button>
          <span style={{ fontFamily: 'var(--font-data)', fontSize: '0.72rem', color: 'var(--ink-muted)', minWidth: 36, textAlign: 'center' }}>{calendarHeight}px</span>
          <button
            onClick={() => setCalendarHeight(h => Math.min(2000, h + 100))}
            style={{ background: 'none', border: '1px solid var(--border)', borderRadius: '3px', width: 22, height: 22, cursor: 'pointer', color: 'var(--ink-muted)', fontSize: '0.85rem', lineHeight: 1, padding: 0 }}
            aria-label="Increase calendar height"
          >+</button>
        </div>
      </div>

      {filterOpen && (
        <div style={{
          marginBottom: '0.75rem',
          padding: '0.75rem',
          border: '1px solid var(--border)',
          borderRadius: '4px',
          background: 'var(--surface)',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
          gap: '1rem',
        }}>
          {/* Course filter column */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
              <span style={{ fontFamily: 'var(--font-data)', fontSize: '0.7rem', fontWeight: 700, color: 'var(--ink-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Courses</span>
              <span style={{ display: 'flex', gap: '0.5rem' }}>
                <button onClick={() => setHiddenCourses(new Set())} style={{ background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-data)', fontSize: '0.7rem', color: 'var(--soundings)', padding: 0 }}>All</button>
                <button onClick={() => setHiddenCourses(new Set(filterableCourses.map(c => c.id)))} style={{ background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-data)', fontSize: '0.7rem', color: 'var(--ink-muted)', padding: 0 }}>None</button>
              </span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', maxHeight: '220px', overflowY: 'auto' }}>
              {filterableCourses.map(({ id, name, color }) => (
                <label key={id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={!hiddenCourses.has(id)}
                    onChange={() => setHiddenCourses(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n })}
                    style={{ accentColor: color, width: '13px', height: '13px', flexShrink: 0 }}
                  />
                  <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 2, background: color, flexShrink: 0 }} />
                  <span style={{ fontFamily: 'var(--font-data)', fontSize: '0.73rem', color: 'var(--ink-muted)' }}>{name}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Location filter column */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
              <span style={{ fontFamily: 'var(--font-data)', fontSize: '0.7rem', fontWeight: 700, color: 'var(--ink-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Locations</span>
              <span style={{ display: 'flex', gap: '0.5rem' }}>
                <button onClick={() => setHiddenLocations(new Set())} style={{ background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-data)', fontSize: '0.7rem', color: 'var(--soundings)', padding: 0 }}>All</button>
                <button onClick={() => setHiddenLocations(new Set(filterableLocations))} style={{ background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-data)', fontSize: '0.7rem', color: 'var(--ink-muted)', padding: 0 }}>None</button>
              </span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', maxHeight: '220px', overflowY: 'auto' }}>
              {filterableLocations.map(loc => (
                <label key={loc} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={!hiddenLocations.has(loc)}
                    onChange={() => setHiddenLocations(prev => { const n = new Set(prev); n.has(loc) ? n.delete(loc) : n.add(loc); return n })}
                    style={{ width: '13px', height: '13px', flexShrink: 0 }}
                  />
                  <span style={{ fontFamily: 'var(--font-data)', fontSize: '0.73rem', color: 'var(--ink-muted)' }}>{loc}</span>
                </label>
              ))}
            </div>
          </div>
        </div>
      )}

      <div
        aria-label="Course calendar"
        style={{
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: '4px',
          padding: '1rem',
          overflowY: 'auto',
        }}
      >
        <Calendar
          localizer={localizer}
          events={visibleEvents}
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
          allDayAccessor="allDay"
          style={{ height: calendarHeight }}
          eventPropGetter={eventStyleGetter}
          components={{ agenda: { event: AgendaEvent } }}
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
