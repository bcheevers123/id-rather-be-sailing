import type { FilterState, CourseCategory, DeliveryFormat, SortField } from '../types/data'

export function encodeFilters(filters: FilterState): URLSearchParams {
  const params = new URLSearchParams()
  if (filters.category) params.set('category', filters.category)
  if (filters.country) params.set('country', filters.country)
  if (filters.region) params.set('region', filters.region)
  if (filters.maxPrice !== undefined) params.set('maxPrice', String(filters.maxPrice))
  if (filters.currency) params.set('currency', filters.currency)
  if (filters.deliveryFormat) params.set('format', filters.deliveryFormat)
  if (filters.hasDates !== undefined) params.set('hasDates', filters.hasDates ? '1' : '0')
  if (filters.hasPrice !== undefined) params.set('hasPrice', filters.hasPrice ? '1' : '0')
  if (filters.provider) params.set('provider', filters.provider)
  if (filters.sortBy) params.set('sortBy', filters.sortBy)
  if (filters.query) params.set('q', filters.query)
  return params
}

export function decodeFilters(params: URLSearchParams): FilterState {
  const filters: FilterState = {}
  const category = params.get('category')
  if (category) filters.category = category as CourseCategory
  const country = params.get('country')
  if (country) filters.country = country
  const region = params.get('region')
  if (region) filters.region = region
  const maxPrice = params.get('maxPrice')
  if (maxPrice) filters.maxPrice = Number(maxPrice)
  const currency = params.get('currency')
  if (currency) filters.currency = currency
  const format = params.get('format')
  if (format) filters.deliveryFormat = format as DeliveryFormat
  const hasDates = params.get('hasDates')
  if (hasDates !== null) filters.hasDates = hasDates === '1'
  const hasPrice = params.get('hasPrice')
  if (hasPrice !== null) filters.hasPrice = hasPrice === '1'
  const provider = params.get('provider')
  if (provider) filters.provider = provider
  const sortBy = params.get('sortBy')
  if (sortBy) filters.sortBy = sortBy as SortField
  const query = params.get('q')
  if (query) filters.query = query
  return filters
}
