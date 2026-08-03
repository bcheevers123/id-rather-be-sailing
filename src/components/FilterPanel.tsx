import type { FilterState, DeliveryFormat, SortField } from '../types/data'

interface Props {
  filters: FilterState
  onChange: (filters: FilterState) => void
  availableCountries: string[]
}

export function FilterPanel({ filters, onChange, availableCountries }: Props) {
  const set = (patch: Partial<FilterState>) => onChange({ ...filters, ...patch })

  return (
    <aside aria-label="Filter results" className="space-y-4 text-sm">
      <div>
        <label htmlFor="filter-country" className="block font-medium text-gray-700 mb-1">Country</label>
        <select
          id="filter-country"
          value={filters.country ?? ''}
          onChange={e => set({ country: e.target.value || undefined })}
          className="w-full rounded border border-gray-300 px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-navy-600"
        >
          <option value="">All countries</option>
          {availableCountries.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      <div>
        <label htmlFor="filter-format" className="block font-medium text-gray-700 mb-1">Delivery format</label>
        <select
          id="filter-format"
          value={filters.deliveryFormat ?? ''}
          onChange={e => set({ deliveryFormat: (e.target.value || undefined) as DeliveryFormat | undefined })}
          className="w-full rounded border border-gray-300 px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-navy-600"
        >
          <option value="">Any format</option>
          <option value="in_person">In person</option>
          <option value="blended">Blended</option>
          <option value="online">Online</option>
        </select>
      </div>

      <fieldset>
        <legend className="block font-medium text-gray-700 mb-1">Show only</legend>
        <label className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={!!filters.hasDates}
            onChange={e => set({ hasDates: e.target.checked || undefined })}
            className="rounded border-gray-300 focus:ring-navy-600" />
          Has upcoming dates
        </label>
        <label className="flex items-center gap-2 cursor-pointer mt-1">
          <input type="checkbox" checked={!!filters.hasPrice}
            onChange={e => set({ hasPrice: e.target.checked || undefined })}
            className="rounded border-gray-300 focus:ring-navy-600" />
          Has public price
        </label>
      </fieldset>

      <div>
        <label htmlFor="filter-sort" className="block font-medium text-gray-700 mb-1">Sort by</label>
        <select
          id="filter-sort"
          value={filters.sortBy ?? 'earliest_date'}
          onChange={e => set({ sortBy: e.target.value as SortField })}
          className="w-full rounded border border-gray-300 px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-navy-600"
        >
          <option value="earliest_date">Earliest upcoming date</option>
          <option value="lowest_price">Lowest price</option>
          <option value="provider_name">Provider name</option>
          <option value="recently_verified">Most recently verified</option>
          <option value="location">Location</option>
        </select>
      </div>

      {Object.keys(filters).filter(k => filters[k as keyof FilterState] !== undefined).length > 0 && (
        <button
          onClick={() => onChange({})}
          className="w-full rounded border border-gray-300 px-3 py-1.5 text-gray-600 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-navy-600"
        >
          Clear all filters
        </button>
      )}
    </aside>
  )
}
