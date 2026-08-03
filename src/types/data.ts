export type FreshnessStatus =
  | 'verified'
  | 'recently_checked'
  | 'stale'
  | 'source_unavailable'
  | 'no_public_schedule'

export type DeliveryFormat = 'in_person' | 'blended' | 'online' | 'unknown'

export type CourseCategory =
  | 'stcw_basic' | 'stcw_advanced' | 'stcw_refresher' | 'stcw_tanker'
  | 'stcw_igf' | 'stcw_helm' | 'stcw_ecdis_naest' | 'gmdss'
  | 'high_voltage' | 'security' | 'deck_yacht' | 'sv_engineering'
  | 'engineering_other' | 'polar' | 'workboat' | 'other'

export interface Course {
  id: string
  official_name: string
  abbreviation: string | null
  aliases: string[]
  category: CourseCategory
  description: string | null
  confusion_note: string | null
  source_pdf_url: string
  source_updated_date: string
  provider_count: number
  earliest_known_date: string | null
  lowest_known_price_gbp: number | null
}

export interface Provider {
  id: string
  official_name: string
  alt_names: string[]
  address: string | null
  city: string | null
  region: string | null
  country: string | null
  postcode: string | null
  lat: number | null
  lng: number | null
  website: string | null
  email: string | null
  telephone: string | null
  not_open_to_public: boolean
}

export interface Approval {
  course_id: string
  provider_id: string
  source_pdf_url: string
  source_updated_date: string
  status: 'active' | 'removed'
  first_seen: string
  last_seen: string
  not_open_to_public: boolean
}

export interface Offering {
  id: string
  course_id: string
  provider_id: string
  start_date: string
  end_date: string
  timezone: string
  duration_days: number | null
  price: number | null
  currency: string | null
  vat_included: boolean | null
  delivery_format: DeliveryFormat
  availability: string | null
  booking_url: string | null
  source_url: string
  last_verified: string
  freshness_status: FreshnessStatus
}

export interface ParseFailure {
  provider_id: string
  reason: string
}

export interface CoverageReport {
  generated_at: string
  total_courses: number
  total_providers: number
  total_approvals: number
  providers_with_dates: number
  providers_with_prices: number
  providers_requiring_manual_review: number
  providers_blocking_automated_collection: number
  providers_no_public_schedule: number
  last_successful_full_refresh: string | null
  parse_failures: ParseFailure[]
}

export interface FilterState {
  category?: CourseCategory
  country?: string
  region?: string
  maxPrice?: number
  currency?: string
  deliveryFormat?: DeliveryFormat
  hasDates?: boolean
  hasPrice?: boolean
  provider?: string
  sortBy?: SortField
  query?: string
}

export type SortField =
  | 'earliest_date'
  | 'lowest_price'
  | 'provider_name'
  | 'recently_verified'
  | 'location'
