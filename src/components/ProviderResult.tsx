import { FreshnessBadge } from './FreshnessBadge'
import type { ProviderResult as ProviderResultType } from '../lib/filters'
import { safeHref } from '../lib/safeHref'

function MapPinIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor"
      strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M8 1.5A4.5 4.5 0 0113.5 6c0 3-5.5 8.5-5.5 8.5S2.5 9 2.5 6A4.5 4.5 0 018 1.5z"/>
      <circle cx="8" cy="6" r="1.5"/>
    </svg>
  )
}

function GlobeIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor"
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
        borderRadius: '4px',
        overflow: 'hidden',
      }}
      aria-label={provider.official_name}
    >
      {/* Header — vessel contact row */}
      <div style={{
        padding: '0.75rem 1rem 0.625rem',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: '1rem',
        flexWrap: 'wrap',
      }}>
        <div className="min-w-0">
          <div style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--ink)', lineHeight: 1.3 }}>
            {provider.official_name}
          </div>
          <div className="flex items-center flex-wrap gap-x-3 gap-y-0.5 mt-0.5">
            {location && (
              <span className="flex items-center gap-1" style={{ color: 'var(--ink-faint)', fontSize: '0.78rem' }}>
                <MapPinIcon />
                {location}
              </span>
            )}
            {websiteHref && (
              <a href={websiteHref} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1 hover:underline"
                style={{ color: 'var(--accent)', fontSize: '0.78rem' }}>
                <GlobeIcon />
                Website
              </a>
            )}
            {provider.telephone && (
              <span style={{ color: 'var(--ink-faint)', fontSize: '0.78rem', fontFamily: 'var(--font-data)' }}>
                {provider.telephone}
              </span>
            )}
          </div>
        </div>
        <FreshnessBadge status={overallStatus} />
      </div>

      {/* Offerings — AIS contact schedule */}
      <div style={{ padding: '0.625rem 1rem' }}>
        {offerings.length > 0 ? (
          <>
            <div style={{
              fontFamily: 'var(--font-data)',
              fontSize: '0.65rem',
              fontWeight: 700,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: 'var(--ink-faint)',
              marginBottom: '0.375rem',
            }}>
              Upcoming dates
            </div>
            <div>
              {offerings.slice(0, 5).map(o => {
                const bookingHref = safeHref(o.booking_url)
                return (
                  <div key={o.id} className="offering-row">
                    <span style={{
                      fontFamily: 'var(--font-data)',
                      fontWeight: 700,
                      fontSize: '0.78rem',
                      color: 'var(--ink)',
                      fontVariantNumeric: 'tabular-nums',
                      whiteSpace: 'nowrap',
                    }}>
                      {o.start_date}{o.end_date && o.end_date !== o.start_date ? ` – ${o.end_date}` : ''}
                    </span>
                    {o.price !== null ? (
                      <span style={{ fontFamily: 'var(--font-data)', fontSize: '0.78rem', color: 'var(--ink-muted)' }}>
                        <strong style={{ color: 'var(--ink)' }}>
                          {o.currency === 'GBP' ? '£' : (o.currency ?? '£')}{o.price.toFixed(0)}
                        </strong>
                        {o.vat_included !== null && (
                          <span style={{ color: 'var(--ink-faint)', fontSize: '0.7rem' }}>
                            {' '}{o.vat_included ? 'inc.VAT' : 'ex.VAT'}
                          </span>
                        )}
                      </span>
                    ) : (
                      <span style={{ color: 'var(--ink-faint)', fontSize: '0.75rem', fontFamily: 'var(--font-data)' }}>
                        POA
                      </span>
                    )}
                    {o.availability && (
                      <span style={{ color: 'var(--ink-faint)', fontSize: '0.72rem', fontFamily: 'var(--font-data)' }}>
                        {o.availability}
                      </span>
                    )}
                    {bookingHref && (
                      <a href={bookingHref} target="_blank" rel="noopener noreferrer"
                        className="btn-phosphor"
                        style={{ marginLeft: 'auto' }}>
                        Book →
                      </a>
                    )}
                  </div>
                )
              })}
            </div>
          </>
        ) : (
          <p style={{ fontSize: '0.8rem', color: 'var(--ink-faint)', fontStyle: 'italic' }}>
            No public dates — contact provider directly
          </p>
        )}
      </div>

      {/* Footer — source attribution */}
      <div style={{
        padding: '0.375rem 1rem',
        background: 'var(--water-800)',
        borderTop: '1px solid var(--border)',
        fontSize: '0.7rem',
        color: 'var(--ink-faint)',
        fontFamily: 'var(--font-data)',
        letterSpacing: '0.01em',
      }}>
        MCA approval ·{' '}
        <a href={approval.source_pdf_url} target="_blank" rel="noopener noreferrer"
          style={{ color: 'var(--ink-faint)' }} className="hover:text-[var(--ink-muted)] hover:underline">
          gov.uk source
        </a>
        {' '}· {approval.source_updated_date}
      </div>
    </article>
  )
}
