# UI Enhancements — Design Spec
**Date:** 2026-08-05

## 1. Sailors Helped Stat on Homepage

**Goal:** Surface the GoatCounter visitor count on the homepage catalogue page, inline below the subtitle.

**Changes:**
- Extract `useSailorsHelped()` from `src/components/RefreshCountdown.tsx` into `src/hooks/useSailorsHelped.ts`
- Update `RefreshCountdown.tsx` to import from the new hook location
- In `src/views/Catalogue.tsx`, below the subtitle line, render:
  > Already helped **1,247 sailors** find their next course.
- "X sailors" is `<strong>` bold; number formatted with `toLocaleString()`
- Loading state: render nothing (no flash)
- Error state: render nothing silently

## 2. Map-First Locations View

**Goal:** Add an interactive Leaflet map above the existing provider directory in `MapView.tsx`.

**Changes:**
- Add a `<MapPanel>` section at the top of `MapView.tsx` using `react-leaflet` (already installed)
- Map height: `h-[400px]`, full width, rounded corners
- One marker per provider that has `lat` and `lng` and is not `not_open_to_public`
- Clicking a marker opens a Leaflet popup with: provider name (bold), region/city, and a "View courses →" link to `/course/` search or provider website
- Default map centre: UK (~54.5°N, -3°W), zoom 6
- The existing search bar and accordion directory sits below unchanged
- No new npm dependencies (react-leaflet + leaflet already in package.json)

## 3. Calendar Course Filter

**Goal:** Allow users to show/hide specific courses from the calendar.

**Changes:**
- Add filter UI above the calendar in `CalendarView.tsx`
- Lists every unique course name present in the current 6-month event window, each with a checkbox (all checked by default)
- "Select all / Clear all" toggle at the top of the list
- Collapsed state shows a single chip: "Filter courses (N hidden)" — click to expand
- Filter state is local to `CalendarView.tsx` (no URL persistence)
- When a course is unchecked, its events are removed from the events array passed to `<Calendar>`

## 4. Grouped Courses Per Calendar Day

**Goal:** Collapse multiple offerings of the same course on the same day into a single calendar event block.

**Changes:**
- In `src/lib/calendarEvents.ts`, add a `groupEvents()` function that merges offerings sharing the same `course_id` and `start_date` into one event
- Grouped event title: `Advanced Firefighting (3)` when count > 1, plain name when count = 1
- `eventStyleGetter` unchanged — colour still keyed on course category
- Click behaviour: if count = 1, open booking URL directly; if count > 1, navigate to `/course/:id` for that course
- Applies to both MONTH and AGENDA views
