import { getFreshnessDisplay } from '../lib/freshness'
import type { FreshnessStatus } from '../types/data'

interface Props {
  status: FreshnessStatus
}

export function FreshnessBadge({ status }: Props) {
  const { label, colour, description } = getFreshnessDisplay(status)
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${colour}`}
      title={description}
      aria-label={`Data status: ${label}. ${description}`}
    >
      {label}
    </span>
  )
}
