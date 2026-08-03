import type { FreshnessStatus } from '../types/data'

const CONFIG: Record<FreshnessStatus, { label: string; cls: string; description: string }> = {
  verified:          { label: 'Verified',          cls: 'badge badge-verified', description: 'Checked within the last 24 hours' },
  recently_checked:  { label: 'Recently checked',  cls: 'badge badge-recent',   description: 'Checked within the last 7 days' },
  stale:             { label: 'Stale',             cls: 'badge badge-stale',    description: 'May be out of date — check failed or overdue' },
  source_unavailable:{ label: 'Source unavailable',cls: 'badge badge-unavail',  description: 'Provider website unreachable — showing last known data' },
  no_public_schedule:{ label: 'No public schedule',cls: 'badge badge-none',     description: 'This provider does not publish their schedule online' },
}

interface Props { status: FreshnessStatus }

export function FreshnessBadge({ status }: Props) {
  const { label, cls, description } = CONFIG[status] ?? CONFIG.no_public_schedule
  return (
    <span className={cls} title={description} aria-label={`Data status: ${label}. ${description}`}>
      {label}
    </span>
  )
}
