import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { Catalogue } from './views/Catalogue'
import { CourseResults } from './views/CourseResults'
import { CalendarView } from './views/CalendarView'

function AnchorIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
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
        style={{ background: 'var(--ink)', borderBottom: '1px solid oklch(28% 0.04 240)' }}
        className="sticky top-0 z-50"
      >
        <div className="mx-auto max-w-5xl px-4 py-0 flex items-center gap-6 h-14">
          <NavLink
            to="/"
            className="flex items-center gap-2.5 text-white font-semibold text-base shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40 rounded"
          >
            <AnchorIcon />
            I'd Rather Be Sailing
          </NavLink>
          <nav className="flex items-center gap-1 ml-4" aria-label="Main navigation">
            {[
              { to: '/', label: 'Courses', exact: true },
              { to: '/calendar', label: 'Calendar', exact: false },
            ].map(({ to, label, exact }) => (
              <NavLink
                key={to}
                to={to}
                end={exact}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded text-sm font-medium transition-colors duration-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40 ` +
                  (isActive
                    ? 'bg-white/15 text-white'
                    : 'text-white/65 hover:text-white hover:bg-white/10')
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <Routes>
        <Route path="/" element={<Catalogue />} />
        <Route path="/course/:id" element={<CourseResults />} />
        <Route path="/calendar" element={<CalendarView />} />
      </Routes>
    </BrowserRouter>
  )
}
