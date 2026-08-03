import { useState, useEffect } from 'react'

function getSecondsUntilMidnightUTC(): number {
  const now = new Date()
  const midnight = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1))
  return Math.max(0, Math.floor((midnight.getTime() - now.getTime()) / 1000))
}

function formatCountdown(secs: number): string {
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const s = secs % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export function RefreshCountdown() {
  const [secs, setSecs] = useState(getSecondsUntilMidnightUTC)

  useEffect(() => {
    const id = setInterval(() => setSecs(getSecondsUntilMidnightUTC()), 1000)
    return () => clearInterval(id)
  }, [])

  return (
    <footer style={{
      borderTop: '1px solid var(--border)',
      padding: '0.5rem 1rem',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '0.5rem',
      background: 'var(--paper)',
    }}>
      <span style={{
        fontFamily: 'var(--font-data)',
        fontSize: '0.62rem',
        letterSpacing: '0.07em',
        textTransform: 'uppercase',
        color: 'var(--ink-faint)',
      }}>
        Next data refresh
      </span>
      <span style={{
        fontFamily: 'var(--font-data)',
        fontSize: '0.68rem',
        fontWeight: 700,
        color: 'var(--navy-400)',
        fontVariantNumeric: 'tabular-nums',
        letterSpacing: '0.04em',
      }}>
        {formatCountdown(secs)}
      </span>
    </footer>
  )
}
