import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { Catalogue } from './views/Catalogue'
import { CourseResults } from './views/CourseResults'
import { CalendarView } from './views/CalendarView'

function AnchorIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="5" r="3"/>
      <line x1="12" y1="8" x2="12" y2="22"/>
      <path d="M5 15H2a10 10 0 0 0 20 0h-3"/>
    </svg>
  )
}

export default function App() {
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <header
        style={{
          background: 'var(--water-800)',
          borderBottom: '1px solid var(--border)',
        }}
        className="sticky top-0 z-50"
      >
        <div className="mx-auto max-w-5xl px-4 flex items-center gap-6 h-12">
          <NavLink
            to="/"
            className="flex items-center gap-2 shrink-0 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--phosphor)] rounded"
            style={{ color: 'var(--accent)', textDecoration: 'none' }}
            aria-label="I'd Rather Be Sailing — home"
          >
            <AnchorIcon />
            <span style={{
              fontFamily: 'var(--font-data)',
              fontWeight: 700,
              fontSize: '0.8125rem',
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
            }}>
              IRBS
            </span>
            <span style={{
              color: 'var(--ink-faint)',
              fontFamily: 'var(--font-data)',
              fontSize: '0.72rem',
              letterSpacing: '0.01em',
              paddingLeft: '0.1rem',
            }} aria-hidden="true">
              / MCA TRAINING FINDER
            </span>
          </NavLink>

          <nav className="flex items-center gap-0.5 ml-auto" aria-label="Main navigation">
            {[
              { to: '/', label: 'COURSES', exact: true },
              { to: '/calendar', label: 'CALENDAR', exact: false },
            ].map(({ to, label, exact }) => (
              <NavLink
                key={to}
                to={to}
                end={exact}
                style={{ textDecoration: 'none' }}
                className={({ isActive }) =>
                  `px-3 py-1 rounded focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--phosphor)] transition-colors duration-100 ` +
                  (isActive
                    ? 'bg-[var(--accent-tint)] text-[var(--accent)] border border-[oklch(40%_0.14_155_/_0.4)]'
                    : 'text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-2)] border border-transparent')
                }
                aria-current={undefined}
              >
                <span style={{
                  fontFamily: 'var(--font-data)',
                  fontSize: '0.68rem',
                  fontWeight: 700,
                  letterSpacing: '0.07em',
                }}>
                  {label}
                </span>
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main id="main-content">
        <Routes>
          <Route path="/" element={<Catalogue />} />
          <Route path="/course/:id" element={<CourseResults />} />
          <Route path="/calendar" element={<CalendarView />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}
