import type { FreshnessStatus } from '../types/data'

interface FreshnessDisplay {
  label: string
  colour: string
  description: string
}

export function getFreshnessDisplay(status: FreshnessStatus): FreshnessDisplay {
  switch (status) {
    case 'verified':
      return { label: 'Verified', colour: 'bg-green-100 text-green-800', description: 'Checked within the last 24 hours' }
    case 'recently_checked':
      return { label: 'Recently checked', colour: 'bg-yellow-100 text-yellow-800', description: 'Checked within the last 7 days' }
    case 'stale':
      return { label: 'Stale', colour: 'bg-orange-100 text-orange-800', description: 'Last known data — check may have failed or be overdue' }
    case 'source_unavailable':
      return { label: 'Source unavailable', colour: 'bg-red-100 text-red-800', description: 'Provider website could not be reached — showing last known data' }
    case 'no_public_schedule':
      return { label: 'No public schedule', colour: 'bg-gray-100 text-gray-700', description: 'This provider does not publish their schedule online' }
  }
}
