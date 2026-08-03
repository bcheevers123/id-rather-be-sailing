import type { Provider, Approval, Offering, FilterState, SortField } from '../types/data'

export interface ProviderResult {
  provider: Provider
  approval: Approval
  offerings: Offering[]
  earliestDate: string | null
  lowestPrice: number | null
}

export function filterProviders(
  providers: Provider[],
  approvals: Approval[],
  offerings: Offering[],
  courseId: string,
  filters: FilterState,
): ProviderResult[] {
  const courseApprovals = approvals.filter(
    a => a.course_id === courseId && a.status === 'active'
  )
  const offeringsByProvider = new Map<string, Offering[]>()
  for (const o of offerings) {
    if (o.course_id !== courseId) continue
    const arr = offeringsByProvider.get(o.provider_id) ?? []
    arr.push(o)
    offeringsByProvider.set(o.provider_id, arr)
  }

  const providerMap = new Map(providers.map(p => [p.id, p]))
  const results: ProviderResult[] = []

  for (const approval of courseApprovals) {
    const provider = providerMap.get(approval.provider_id)
    if (!provider) continue

    const providerOfferings = offeringsByProvider.get(provider.id) ?? []
    const today = new Date().toISOString().slice(0, 10)
    const futureOfferings = providerOfferings.filter(o => o.start_date >= today)

    if (filters.country && provider.country !== filters.country) continue
    if (filters.region && provider.region !== filters.region) continue
    if (filters.provider && provider.id !== filters.provider) continue
    if (filters.deliveryFormat && !futureOfferings.some(o => o.delivery_format === filters.deliveryFormat)) continue
    if (filters.hasDates && futureOfferings.length === 0) continue
    if (filters.hasPrice && !futureOfferings.some(o => o.price !== null)) continue
    if (filters.maxPrice !== undefined) {
      const gbpOfferings = futureOfferings.filter(o => o.currency === 'GBP' && o.price !== null)
      if (gbpOfferings.length > 0 && Math.min(...gbpOfferings.map(o => o.price!)) > filters.maxPrice) continue
    }

    const sortedOfferings = [...futureOfferings].sort((a, b) => a.start_date.localeCompare(b.start_date))
    const earliestDate = sortedOfferings[0]?.start_date ?? null
    const gbpPrices = sortedOfferings.filter(o => o.currency === 'GBP' && o.price !== null).map(o => o.price!)
    const lowestPrice = gbpPrices.length > 0 ? Math.min(...gbpPrices) : null

    results.push({ provider, approval, offerings: sortedOfferings, earliestDate, lowestPrice })
  }

  return results
}

export function sortProviderResults(results: ProviderResult[], sortBy: SortField): ProviderResult[] {
  const sorted = [...results]
  switch (sortBy) {
    case 'earliest_date':
      return sorted.sort((a, b) => {
        if (!a.earliestDate && !b.earliestDate) return 0
        if (!a.earliestDate) return 1
        if (!b.earliestDate) return -1
        return a.earliestDate.localeCompare(b.earliestDate)
      })
    case 'lowest_price':
      return sorted.sort((a, b) => {
        if (a.lowestPrice === null && b.lowestPrice === null) return 0
        if (a.lowestPrice === null) return 1
        if (b.lowestPrice === null) return -1
        return a.lowestPrice - b.lowestPrice
      })
    case 'provider_name':
      return sorted.sort((a, b) => a.provider.official_name.localeCompare(b.provider.official_name))
    case 'recently_verified': {
      const statusOrder: Record<string, number> = { verified: 0, recently_checked: 1, stale: 2, source_unavailable: 3, no_public_schedule: 4 }
      return sorted.sort((a, b) => {
        const aStatus = a.offerings[0]?.freshness_status ?? 'no_public_schedule'
        const bStatus = b.offerings[0]?.freshness_status ?? 'no_public_schedule'
        return (statusOrder[aStatus] ?? 5) - (statusOrder[bStatus] ?? 5)
      })
    }
    case 'location':
      return sorted.sort((a, b) => (a.provider.city ?? '').localeCompare(b.provider.city ?? ''))
    default:
      return sorted
  }
}
