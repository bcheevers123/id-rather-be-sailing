import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import { Catalogue } from './views/Catalogue'
import { CourseResults } from './views/CourseResults'
import { CalendarView } from './views/CalendarView'

export default function App() {
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <nav className="bg-navy-800 px-4 py-3 flex items-center gap-6">
        <Link to="/" className="text-white font-semibold text-lg">I'd Rather Be Sailing</Link>
        <Link to="/" className="text-navy-100 text-sm hover:text-white">Courses</Link>
        <Link to="/calendar" className="text-navy-100 text-sm hover:text-white">Calendar</Link>
      </nav>
      <Routes>
        <Route path="/" element={<Catalogue />} />
        <Route path="/course/:id" element={<CourseResults />} />
        <Route path="/calendar" element={<CalendarView />} />
      </Routes>
    </BrowserRouter>
  )
}
