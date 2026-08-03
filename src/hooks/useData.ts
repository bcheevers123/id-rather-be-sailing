import { useState, useEffect } from 'react'
import type { Course, Provider, Approval, Offering, CoverageReport } from '../types/data'

const BASE = import.meta.env.BASE_URL

interface DataStore {
  courses: Course[]
  providers: Provider[]
  approvals: Approval[]
  offerings: Offering[]
  coverageReport: CoverageReport | null
  loading: boolean
  error: string | null
}

async function loadJson<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE}data/${path}`)
  if (!resp.ok) throw new Error(`Failed to load ${path}: ${resp.status}`)
  return resp.json() as Promise<T>
}

export function useData(): DataStore {
  const [state, setState] = useState<DataStore>({
    courses: [],
    providers: [],
    approvals: [],
    offerings: [],
    coverageReport: null,
    loading: true,
    error: null,
  })

  useEffect(() => {
    Promise.all([
      loadJson<Course[]>('courses.json'),
      loadJson<Provider[]>('providers.json'),
      loadJson<Approval[]>('approvals.json'),
      loadJson<Offering[]>('offerings.json'),
      loadJson<CoverageReport>('coverage_report.json'),
    ])
      .then(([courses, providers, approvals, offerings, coverageReport]) => {
        setState({ courses, providers, approvals, offerings, coverageReport, loading: false, error: null })
      })
      .catch((err: Error) => {
        setState(s => ({ ...s, loading: false, error: err.message }))
      })
  }, [])

  return state
}
