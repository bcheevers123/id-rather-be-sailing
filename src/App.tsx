import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { Catalogue } from './views/Catalogue'
import { CourseResults } from './views/CourseResults'
import { CalendarView } from './views/CalendarView'
import { PathwaysView } from './views/PathwaysView'
import { OtherProviders } from './views/OtherProviders'
import { MapView } from './views/MapView'
import { ChartVesselsBackground } from './components/ChartVessels'
import { RefreshCountdown } from './components/RefreshCountdown'

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
      {/* Admiralty navy header — chart cover colour */}
      <header style={{
        background: 'var(--navy-950)',
        borderBottom: '3px solid var(--chart-red)',
      }} className="sticky top-0 z-50">
        <div className="mx-auto max-w-5xl px-4 flex items-center gap-6 h-14">
          <NavLink
            to="/"
            className="flex items-center gap-2.5 shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40 rounded"
            style={{ color: '#ffffff', textDecoration: 'none' }}
            aria-label="I'd Rather Be Sailing — home"
          >
            <AnchorIcon />
            <span className="hidden sm:inline" style={{
              fontFamily: 'var(--font-ui)',
              fontWeight: 700,
              fontSize: '1rem',
              letterSpacing: '-0.01em',
              whiteSpace: 'nowrap',
            }}>
              I'd Rather Be Sailing
            </span>
          </NavLink>

          <nav className="flex items-center gap-0.5 ml-auto shrink-0" aria-label="Main navigation">
            {[
              { to: '/', label: 'Courses', exact: true },
              { to: '/calendar', label: 'Calendar', exact: false },
              { to: '/pathways', label: 'Pathways', exact: false },
              { to: '/map', label: 'Locations', exact: false },
              { to: '/other-providers', label: 'Other Providers', exact: false },
            ].map(({ to, label, exact }) => (
              <NavLink
                key={to}
                to={to}
                end={exact}
                style={{ textDecoration: 'none' }}
                className={({ isActive }) =>
                  `px-2 sm:px-3 py-1.5 rounded text-xs sm:text-sm font-medium transition-colors duration-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40 whitespace-nowrap ` +
                  (isActive
                    ? 'bg-white/20 text-white'
                    : 'text-white/65 hover:text-white hover:bg-white/10')
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <ChartVesselsBackground />
      <main id="main-content" style={{ position: 'relative', zIndex: 1 }}>
        <Routes>
          <Route path="/" element={<Catalogue />} />
          <Route path="/course/:id" element={<CourseResults />} />
          <Route path="/calendar" element={<CalendarView />} />
          <Route path="/pathways" element={<PathwaysView />} />
          <Route path="/map" element={<MapView />} />
          <Route path="/other-providers" element={<OtherProviders />} />
        </Routes>
      </main>
      <RefreshCountdown />
    </BrowserRouter>
  )
}
