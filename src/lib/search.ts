import Fuse from 'fuse.js'
import type { Course } from '../types/data'

export function buildSearchIndex(courses: Course[]): Fuse<Course> {
  return new Fuse(courses, {
    threshold: 0.3,
    includeScore: true,
    keys: [
      { name: 'official_name', weight: 2 },
      { name: 'abbreviation', weight: 2 },
      { name: 'aliases', weight: 1.5 },
      { name: 'description', weight: 0.5 },
    ],
  })
}

export function searchCourses(fuse: Fuse<Course>, query: string): Course[] {
  if (!query.trim()) return []
  return fuse.search(query).map(r => r.item)
}
