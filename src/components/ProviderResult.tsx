import { FreshnessBadge } from './FreshnessBadge'
import type { ProviderResult as ProviderResultType } from '../lib/filters'
import { safeHref } from '../lib/safeHref'

function MapPinIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor"
      strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M8 1.5A4.5 4.5 0 0113.5 6c0 3-5.5 8.5-5.5 8.5S2.5 9 2.5 6A4.5 4.5 0 018 1.5z"/>
      <circle cx="8" cy="6" r="1.5"/>
    </svg>
  )
}

function GlobeIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor"
      strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
      <circle cx="8" cy="8" r="6.5"/>
      <path d="M1.5 8h13M8 1.5C6.5 3.5 5.5 5.6 5.5 8s1 4.5 2.5 6.5M8 1.5C9.5 3.5 10.5 5.6 10.5 8s-1 4.5-2.5 6.5"/>
    </svg>
  )
}

interface Props {
  result: ProviderResultType
}

export function ProviderResultCard({ result }: Props) {
  const { provider, approval, offerings } = result
  const overallStatus = offerings.length > 0
    ? offerings[0].freshness_status
    : 'no_public_schedule'

  const location = [provider.city, provider.region, provider.country].filter(Boolean).join(', ')
  const websiteHref = safeHref(provider.website)

  return (
    <article
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: '8px',
        overflow: 'hidden',
      }}
      aria-label={provider.official_name}
    >
      {/* Header */}
      <div style={{ padding: '1rem 1rem 0.75rem', borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-start justify-between gap-2 flex-wrap">
          <div className="min-w-0">
            <h3 style={{ color: 'var(--ink)', fontWeight: 600, fontSize: '0.9375rem', lineHeight: 1.3 }}>
              {provider.official_name}
            </h3>
            {location && (
              <p className="flex items-center gap-1 mt-0.5" style={{ color: 'var(--ink-muted)', fontSize: '0.8125rem' }}>
                <MapPinIcon />
                {location}
              </p>
            )}
          </div>
          <FreshnessBadge status={overallStatus} />
        </div>

        {/* Contact row */}
        <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2" style={{ fontSize: '0.8125rem' }}>
          {websiteHref && (
            <a href={websiteHref} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1 hover:underline"
              style={{ color: 'var(--accent)' }}>
              <GlobeIcon />
              Website
            </a>
          )}
          {provider.telephone && (
            <span style={{ color: 'var(--ink-muted)' }}>{provider.telephone}</span>
          )}
          {provider.email && (
            <a href={`mailto:${provider.email}`}
              style={{ color: 'var(--accent)' }}
              className="hover:underline">
              {provider.email}
            </a>
          )}
        </div>
      </div>

      {/* Offerings */}
      <div style={{ padding: '0.75rem 1rem' }}>
        {offerings.length > 0 ? (
          <>
            <p style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--ink-muted)', marginBottom: '0.5rem', letterSpacing: '0.01em' }}>
              Upcoming dates
            </p>
            <div>
              {offerings.slice(0, 5).map(o => {
                const bookingHref = safeHref(o.booking_url)
                return (
                  <div key={o.id} className="offering-row">
                    <span style={{ fontWeight: 600, color: 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>
                      {o.start_date}{o.end_date && o.end_date !== o.start_date ? ` – ${o.end_date}` : ''}
                    </span>
                    {o.price !== null ? (
                      <span style={{ color: 'var(--ink-muted)' }}>
                        {o.currency}{' '}
                        <strong style={{ color: 'var(--ink)' }}>{o.price.toFixed(0)}</strong>
                        {o.vat_included !== null && (
                          <span style={{ color: 'var(--ink-faint)', fontSize: '0.75rem' }}>
                            {' '}{o.vat_included ? 'inc. VAT' : 'ex. VAT'}
                          </span>
                        )}
                      </span>
                    ) : (
                      <span style={{ color: 'var(--ink-faint)' }}>Price on request</span>
                    )}
                    {o.availability && (
                      <span style={{ color: 'var(--ink-faint)', fontSize: '0.75rem' }}>{o.availability}</span>
                    )}
                    {bookingHref && (
                      <a href={bookingHref} target="_blank" rel="noopener noreferrer"
                        style={{
                          marginLeft: 'auto',
                          color: 'var(--surface)',
                          background: 'var(--accent)',
                          borderRadius: '5px',
                          padding: '0.2rem 0.65rem',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          textDecoration: 'none',
                          whiteSpace: 'nowrap',
                          transition: 'background 100ms',
                        }}
                        className="hover:bg-[var(--accent-dim)]">
                        Book →
                      </a>
                    )}
                  </div>
                )
              })}
            </div>
          </>
        ) : (
          <p style={{ fontSize: '0.8125rem', color: 'var(--ink-muted)', fontStyle: 'italic' }}>
            No public dates — contact provider directly
          </p>
        )}
      </div>

      {/* Footer */}
      <div style={{
        padding: '0.5rem 1rem',
        background: 'var(--surface-2)',
        borderTop: '1px solid var(--border)',
        fontSize: '0.75rem',
        color: 'var(--ink-faint)',
      }}>
        MCA approval:{' '}
        <a href={approval.source_pdf_url} target="_blank" rel="noopener noreferrer"
          style={{ color: 'var(--ink-muted)' }} className="hover:underline">
          source document
        </a>
        {' '}· updated {approval.source_updated_date}
      </div>
    </article>
  )
}
