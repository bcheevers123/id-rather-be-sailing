import type { FreshnessStatus } from '../types/data'

const CONFIG: Record<FreshnessStatus, { label: string; cls: string; description: string }> = {
  verified:          { label: 'Live',      cls: 'badge badge-verified', description: 'Checked within the last 24 hours' },
  recently_checked:  { label: 'Recent',    cls: 'badge badge-recent',   description: 'Checked within the last 7 days' },
  stale:             { label: 'Stale',     cls: 'badge badge-stale',    description: 'May be out of date' },
  source_unavailable:{ label: 'Offline',   cls: 'badge badge-unavail',  description: 'Provider website unreachable' },
  no_public_schedule:{ label: 'No sched',  cls: 'badge badge-none',     description: 'Provider does not publish schedule' },
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
