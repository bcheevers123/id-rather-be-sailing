import { useState, useEffect } from 'react'

export function useSailorsHelped(): number | null {
  const [count, setCount] = useState<number | null>(null)

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data/stats.json`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.total_visitors != null) setCount(data.total_visitors as number)
      })
      .catch(() => {})
  }, [])

  return count
}
