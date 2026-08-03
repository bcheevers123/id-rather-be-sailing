import { FreshnessBadge } from './FreshnessBadge'
import type { ProviderResult as ProviderResultType } from '../lib/filters'
import { safeHref } from '../lib/safeHref'

interface Props {
  result: ProviderResultType
}

export function ProviderResultCard({ result }: Props) {
  const { provider, approval, offerings } = result
  const overallStatus = offerings[0]?.freshness_status ?? 'no_public_schedule'

  return (
    <article
      className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
      aria-label={provider.official_name}
    >
      <div className="flex items-start justify-between gap-2 flex-wrap">
        <div>
          <h3 className="text-base font-semibold text-gray-900">{provider.official_name}</h3>
          <p className="text-sm text-gray-500">
            {[provider.city, provider.region, provider.country].filter(Boolean).join(', ')}
          </p>
          {provider.address && (
            <p className="mt-0.5 text-xs text-gray-400">{provider.address}</p>
          )}
        </div>
        <FreshnessBadge status={overallStatus} />
      </div>

      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm">
        {safeHref(provider.website) && (
          <a href={safeHref(provider.website)} target="_blank" rel="noopener noreferrer"
            className="text-navy-700 underline hover:text-navy-900 focus:outline-none focus:ring-2 focus:ring-navy-600">
            Website
          </a>
        )}
        {provider.telephone && <span className="text-gray-600">{provider.telephone}</span>}
        {provider.email && (
          <a href={`mailto:${provider.email}`} rel="noopener noreferrer"
            className="text-navy-700 underline hover:text-navy-900 focus:outline-none focus:ring-2 focus:ring-navy-600">
            {provider.email}
          </a>
        )}
      </div>

      {offerings.length > 0 ? (
        <div className="mt-3">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500 mb-1">Upcoming dates</p>
          <ul className="space-y-1">
            {offerings.slice(0, 5).map(o => (
              <li key={o.id} className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-sm">
                <span className="font-medium text-gray-900">{o.start_date}–{o.end_date}</span>
                {o.price !== null ? (
                  <span className="text-gray-600">
                    {o.currency} {o.price.toFixed(2)}
                    {o.vat_included !== null && (
                      <span className="text-gray-400 text-xs"> ({o.vat_included ? 'incl. VAT' : 'excl. VAT'})</span>
                    )}
                  </span>
                ) : (
                  <span className="text-gray-400">Price not published</span>
                )}
                {safeHref(o.booking_url) && (
                  <a href={safeHref(o.booking_url)} target="_blank" rel="noopener noreferrer"
                    className="text-navy-700 underline text-xs hover:text-navy-900 focus:outline-none focus:ring-2 focus:ring-navy-600">
                    Book →
                  </a>
                )}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="mt-3 rounded bg-gray-50 px-3 py-2 text-sm text-gray-500">
          No public dates found — contact provider directly
        </div>
      )}

      <div className="mt-3 border-t border-gray-100 pt-2 text-xs text-gray-400">
        MCA approval:{' '}
        <a href={approval.source_pdf_url} target="_blank" rel="noopener noreferrer"
          className="underline hover:text-gray-600">
          Source document
        </a>
        {' '}(updated {approval.source_updated_date})
      </div>
    </article>
  )
}
