# UI Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four UI enhancements: homepage sailors-helped stat, map-first Locations view, calendar course filter, and grouped calendar events.

**Architecture:** Extract `useSailorsHelped` to a shared hook; add a Leaflet map panel above the existing provider directory in `MapView.tsx`; add a collapsible course-filter checkbox panel to `CalendarView.tsx`; replace one-event-per-offering in `calendarEvents.ts` with grouped events that collapse same-course same-day offerings.

**Tech Stack:** React 18, TypeScript, react-leaflet + leaflet (already installed), react-big-calendar, date-fns, Vite

## Global Constraints

- No new npm dependencies — all required libs already in package.json
- Follow existing inline-style patterns (no new Tailwind utility classes beyond what already exists)
- GoatCounter API URL: `https://idratherbesailing.goatcounter.com/api/v0/stats/total`
- Map default centre: lat 54.5, lng -3.0, zoom 6
- Filter state is local to CalendarView — no URL persistence
- All-day events use react-big-calendar's exclusive-end convention (end = last_date + 1 day)

---

### Task 1: Extract `useSailorsHelped` to a shared hook

**Files:**
- Create: `src/hooks/useSailorsHelped.ts`
- Modify: `src/components/RefreshCountdown.tsx`

**Interfaces:**
- Produces: `useSailorsHelped(): number | null` — exported from `src/hooks/useSailorsHelped.ts`

- [ ] **Step 1: Create the hook file**

```typescript
// src/hooks/useSailorsHelped.ts
import { useState, useEffect } from 'react'

export function useSailorsHelped(): number | null {
  const [count, setCount] = useState<number | null>(null)

  useEffect(() => {
    fetch('https://idratherbesailing.goatcounter.com/api/v0/stats/total', {
      headers: { Accept: 'application/json' },
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.total != null) setCount(data.total as number)
      })
      .catch(() => { /* silently ignore — counter is decorative */ })
  }, [])

  return count
}
```

- [ ] **Step 2: Update RefreshCountdown to import from the new hook**

In `src/components/RefreshCountdown.tsx`:
- Remove the local `useSailorsHelped` function definition (lines 16–32)
- Add import at top: `import { useSailorsHelped } from '../hooks/useSailorsHelped'`

The rest of RefreshCountdown.tsx is unchanged.

- [ ] **Step 3: Build check**

Run: `npm run build`
Expected: zero TypeScript errors, build succeeds

- [ ] **Step 4: Commit**

```bash
git add src/hooks/useSailorsHelped.ts src/components/RefreshCountdown.tsx
git commit -m "refactor: extract useSailorsHelped into shared hook"
```

---

### Task 2: Sailors-helped stat on homepage

**Files:**
- Modify: `src/views/Catalogue.tsx`

**Interfaces:**
- Consumes: `useSailorsHelped(): number | null` from `src/hooks/useSailorsHelped`

- [ ] **Step 1: Add the import to Catalogue.tsx**

Add to the imports block at the top of `src/views/Catalogue.tsx`:
```typescript
import { useSailorsHelped } from '../hooks/useSailorsHelped'
```

- [ ] **Step 2: Call the hook inside the Catalogue component**

Inside `export function Catalogue()`, after the existing hooks, add:
```typescript
const sailorsHelped = useSailorsHelped()
```

- [ ] **Step 3: Add the stat line below the subtitle**

In `Catalogue.tsx`, find this paragraph (the subtitle, around line 221):
```tsx
<p style={{ fontSize: '0.8125rem', color: 'var(--ink-muted)', lineHeight: 1.6, margin: 0 }}>
  Every MCA-approved course with live dates and prices, refreshed daily.
</p>
```

Replace it with:
```tsx
<p style={{ fontSize: '0.8125rem', color: 'var(--ink-muted)', lineHeight: 1.6, margin: 0 }}>
  Every MCA-approved course with live dates and prices, refreshed daily.
</p>
{sailorsHelped !== null && (
  <p style={{ fontSize: '0.8125rem', color: 'var(--ink-muted)', lineHeight: 1.6, margin: '0.2rem 0 0' }}>
    Already helped{' '}
    <strong style={{ color: 'var(--soundings)', fontWeight: 700 }}>
      {sailorsHelped.toLocaleString()} sailors
    </strong>
    {' '}find their next course.
  </p>
)}
```

- [ ] **Step 4: Build check**

Run: `npm run build`
Expected: zero TypeScript errors

- [ ] **Step 5: Commit**

```bash
git add src/views/Catalogue.tsx
git commit -m "feat: show sailors-helped stat on homepage"
```

---

### Task 3: Map panel in Locations view

**Files:**
- Modify: `src/views/MapView.tsx`

**Interfaces:**
- Consumes: `Provider` (with `lat: number | null`, `lng: number | null`) from `src/types/data`
- Consumes: react-leaflet `MapContainer`, `TileLayer`, `Marker`, `Popup` — already available

- [ ] **Step 1: Add react-leaflet imports to MapView.tsx**

At the top of `src/views/MapView.tsx`, add:
```typescript
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

// Fix Leaflet's broken default icon paths in bundled environments
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
})
```

- [ ] **Step 2: Add the ProvidersMap component above the directory**

Add this component definition in `MapView.tsx` above the `MapView` export function:
```tsx
function ProvidersMap({ providers }: { providers: Provider[] }) {
  const mappable = providers.filter(
    p => !p.not_open_to_public && p.lat !== null && p.lng !== null
  ) as (Provider & { lat: number; lng: number })[]

  return (
    <div style={{ height: '400px', borderRadius: '6px', overflow: 'hidden', border: '1px solid var(--border)', marginBottom: '1.5rem' }}>
      <MapContainer
        center={[54.5, -3.0]}
        zoom={6}
        style={{ height: '100%', width: '100%' }}
        scrollWheelZoom={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {mappable.map(p => (
          <Marker key={p.id} position={[p.lat, p.lng]}>
            <Popup>
              <strong style={{ fontSize: '0.85rem' }}>{p.official_name}</strong>
              {(p.region || p.city) && (
                <div style={{ fontSize: '0.75rem', color: '#555', marginTop: '2px' }}>
                  {p.city ?? p.region?.replace(/\n/g, ', ')}
                </div>
              )}
              {p.website && (
                <div style={{ marginTop: '4px' }}>
                  <a href={p.website} target="_blank" rel="noopener noreferrer"
                    style={{ fontSize: '0.75rem', color: '#1a5276' }}>
                    View website →
                  </a>
                </div>
              )}
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  )
}
```

- [ ] **Step 3: Insert ProvidersMap into the MapView render**

In the `MapView` return statement, find the `{/* Header */}` div and the search input `{/* Search */}` div. Insert `<ProvidersMap>` between the search block and the UK sections block:

Replace:
```tsx
      {/* UK sections */}
      {ukRegions.length > 0 && (
```

With:
```tsx
      {/* Interactive map */}
      <ProvidersMap providers={providers} />

      {/* UK sections */}
      {ukRegions.length > 0 && (
```

Note: pass the unfiltered `providers` to the map (so search doesn't hide map pins), while the directory below continues using `filtered`.

- [ ] **Step 4: Build check**

Run: `npm run build`
Expected: zero TypeScript errors. If you see "Cannot find module 'leaflet/dist/images/...'" errors, the Vite config may need `assetsInclude`. Check the error and add to `vite.config.ts` if needed:
```typescript
assetsInclude: ['**/*.png']
```

- [ ] **Step 5: Commit**

```bash
git add src/views/MapView.tsx
git commit -m "feat: add interactive Leaflet map to Locations view"
```

---

### Task 4: Grouped events in calendarEvents.ts

**Files:**
- Modify: `src/lib/calendarEvents.ts`
- Modify: `src/views/CalendarView.tsx` (update click handler)

**Interfaces:**
- Produces: updated `CalEvent` — `resource` now has `offerings: Offering[]` (plural) in addition to the singular `offering` kept for backward compat; new field `groupCount: number`
- Produces: `groupCalendarEvents(events: CalEvent[]): CalEvent[]` — exported

The grouped CalEvent uses the first offering as `resource.offering` (for backward compat with tooltip), sets `groupCount > 1` when merged, and sets title to `"AFF (3)"` format when grouped.

- [ ] **Step 1: Update the CalEvent type and add groupCalendarEvents**

In `src/lib/calendarEvents.ts`, update `CalEventResource` and `CalEvent`, then add the grouping function:

```typescript
export interface CalEventResource {
  offering: Offering          // first offering (kept for compat)
  offerings: Offering[]       // all offerings in this group
  course: Course
  provider: Provider          // provider of the first offering
}

export interface CalEvent {
  id: string
  title: string
  start: Date
  end: Date
  allDay: true
  color: string
  groupCount: number          // 1 for ungrouped, >1 for merged
  resource: CalEventResource
}
```

Add this function after `toCalendarEvents`:
```typescript
export function groupCalendarEvents(events: CalEvent[]): CalEvent[] {
  // Group by course_id + start_date string (YYYY-MM-DD)
  const key = (e: CalEvent) =>
    `${e.resource.course.id}::${e.start.toISOString().slice(0, 10)}`

  const groups = new Map<string, CalEvent[]>()
  for (const e of events) {
    const k = key(e)
    ;(groups.get(k) ?? (groups.set(k, []), groups.get(k)!)).push(e)
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
```

Also update `toCalendarEvents` to initialise `offerings` and `groupCount` on each event it creates:

In the `events.push({...})` call, add:
```typescript
      groupCount: 1,
      resource: { offering, offerings: [offering], course, provider },
```

- [ ] **Step 2: Apply grouping in CalendarView.tsx**

In `src/views/CalendarView.tsx`:

Add `groupCalendarEvents` to the import:
```typescript
import { toCalendarEvents, courseColour, groupCalendarEvents } from '../lib/calendarEvents'
```

Update the `events` memo to apply grouping:
```typescript
  const events = useMemo(
    () => groupCalendarEvents(toCalendarEvents(filteredOfferings, courses, providers)),
    [filteredOfferings, courses, providers]
  )
```

Update `handleSelectEvent` to handle grouped events:
```typescript
  const handleSelectEvent = useCallback((event: CalEvent) => {
    if (event.groupCount > 1) {
      // Navigate to course results page for this course
      window.location.href = `${import.meta.env.BASE_URL}course/${event.resource.course.id}`
    } else {
      const url = safeHref(event.resource.offering.booking_url)
      if (url) window.open(url, '_blank', 'noopener,noreferrer')
    }
  }, [])
```

Update the `legendCourses` memo — it references `e.resource.course`, which is unchanged, so no edits needed.

Update the session count in the subtitle to reflect grouped count:
```tsx
<p style={{ fontSize: '0.8rem', color: 'var(--ink-faint)', fontFamily: 'var(--font-data)' }}>
  {events.length} upcoming {events.length === 1 ? 'session' : 'sessions'} with confirmed dates · click to book
</p>
```
This is already fine — it will now reflect the grouped count naturally.

- [ ] **Step 3: Build check**

Run: `npm run build`
Expected: zero TypeScript errors

- [ ] **Step 4: Commit**

```bash
git add src/lib/calendarEvents.ts src/views/CalendarView.tsx
git commit -m "feat: group same-course same-day offerings in calendar"
```

---

### Task 5: Calendar course filter panel

**Files:**
- Modify: `src/views/CalendarView.tsx`

**Interfaces:**
- Consumes: `events` (post-grouping) to derive the list of unique course names with checkboxes

- [ ] **Step 1: Add filter state to CalendarView**

Inside `export function CalendarView()`, after the existing state declarations, add:
```typescript
  const [filterOpen, setFilterOpen] = useState(false)
  const [hiddenCourses, setHiddenCourses] = useState<Set<string>>(new Set())
```

- [ ] **Step 2: Derive the list of filterable courses**

Add a memo for the full set of courses present in the event window (before hiding):
```typescript
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
```

Apply the filter to produce `visibleEvents`:
```typescript
  const visibleEvents = useMemo(
    () => hiddenCourses.size === 0
      ? events
      : events.filter(e => !hiddenCourses.has(e.resource.course.id)),
    [events, hiddenCourses]
  )
```

- [ ] **Step 3: Update the Calendar to use visibleEvents**

Change `events={events}` in the `<Calendar>` component to `events={visibleEvents}`.

Also update the session count line to use `visibleEvents`:
```tsx
<p style={{ fontSize: '0.8rem', color: 'var(--ink-faint)', fontFamily: 'var(--font-data)' }}>
  {visibleEvents.length} upcoming {visibleEvents.length === 1 ? 'session' : 'sessions'} with confirmed dates · click to book
</p>
```

- [ ] **Step 4: Add the filter panel UI**

Add this JSX block between the `legendCourses` section and the calendar `<div aria-label="Course calendar">`:

```tsx
      {/* Course filter panel */}
      {filterableCourses.length > 0 && (
        <div style={{ marginBottom: '0.75rem' }}>
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
              color: hiddenCourses.size > 0 ? 'var(--chart-red)' : 'var(--ink-muted)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
            }}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
              <line x1="4" y1="6" x2="20" y2="6"/><line x1="8" y1="12" x2="16" y2="12"/><line x1="11" y1="18" x2="13" y2="18"/>
            </svg>
            {hiddenCourses.size > 0
              ? `Filter courses (${hiddenCourses.size} hidden)`
              : 'Filter courses'}
          </button>

          {filterOpen && (
            <div style={{
              marginTop: '0.5rem',
              padding: '0.75rem',
              border: '1px solid var(--border)',
              borderRadius: '4px',
              background: 'var(--surface)',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.4rem',
              maxHeight: '260px',
              overflowY: 'auto',
            }}>
              {/* Select all / Clear all */}
              <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '0.25rem' }}>
                <button
                  onClick={() => setHiddenCourses(new Set())}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-data)', fontSize: '0.72rem', color: 'var(--soundings)', padding: 0 }}
                >
                  Select all
                </button>
                <button
                  onClick={() => setHiddenCourses(new Set(filterableCourses.map(c => c.id)))}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-data)', fontSize: '0.72rem', color: 'var(--ink-muted)', padding: 0 }}
                >
                  Clear all
                </button>
              </div>

              {filterableCourses.map(({ id, name, color }) => (
                <label key={id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={!hiddenCourses.has(id)}
                    onChange={() => {
                      setHiddenCourses(prev => {
                        const next = new Set(prev)
                        if (next.has(id)) next.delete(id)
                        else next.add(id)
                        return next
                      })
                    }}
                    style={{ accentColor: color, width: '13px', height: '13px' }}
                  />
                  <span style={{
                    display: 'inline-block',
                    width: 8, height: 8,
                    borderRadius: 2,
                    background: color,
                    flexShrink: 0,
                  }} />
                  <span style={{ fontFamily: 'var(--font-data)', fontSize: '0.75rem', color: 'var(--ink-muted)' }}>
                    {name}
                  </span>
                </label>
              ))}
            </div>
          )}
        </div>
      )}
```

- [ ] **Step 5: Build check**

Run: `npm run build`
Expected: zero TypeScript errors

- [ ] **Step 6: Commit**

```bash
git add src/views/CalendarView.tsx
git commit -m "feat: add course filter panel to calendar view"
```

---

### Task 6: Push to GitHub and verify deploy

- [ ] **Step 1: Final build check**

Run: `npm run build`
Expected: clean build, `dist/` generated

- [ ] **Step 2: Push**

```bash
git push origin main
```

- [ ] **Step 3: Verify CI**

Check GitHub Actions — the Deploy workflow should run and succeed.
