import { useState, useEffect } from 'react'

export function useSailorsHelped(): number | null {
  const [count, setCount] = useState<number | null>(null)

  useEffect(() => {
    fetch('https://idratherbesailing.goatcounter.com/api/v0/stats/total', {
      headers: { Accept: 'application/json' },
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.total != null) setCount(data.total as number)
      })
      .catch(() => { /* silently ignore — counter is decorative */ })
  }, [])

  return count
}
