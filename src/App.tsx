import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Catalogue } from './views/Catalogue'
import { CourseResults } from './views/CourseResults'

export default function App() {
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <Routes>
        <Route path="/" element={<Catalogue />} />
        <Route path="/course/:id" element={<CourseResults />} />
      </Routes>
    </BrowserRouter>
  )
}
