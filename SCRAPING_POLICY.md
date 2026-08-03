# Scraping Policy

## Before scraping any site

1. Check for a public API or structured data feed first.
2. Fetch and read `robots.txt`. If the relevant path is disallowed, do not scrape — mark the provider `no_public_schedule`.
3. Review the site's terms of use for restrictions on automated access.

## During collection

- User-Agent: `Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; +https://github.com/bcheevers123/id-rather-be-sailing)`
- Minimum 2-second delay between requests to the same domain.
- Use `If-None-Match` / `If-Modified-Since` conditional requests where supported.
- Cache responses; do not re-download unchanged content.
- Do not bypass CAPTCHAs, authentication, or anti-bot measures.
- Do not scrape login-required or private pages.
- Do not disguise automated activity.

## When collection is not possible

Keep the provider in the approved-centre results. Set `freshness_status: no_public_schedule`. Link to their website. Record the reason in `PROVIDER_COVERAGE.md`.

## Rate limits

No more than 1 request per 2 seconds per domain. The pipeline processes providers sequentially within each domain.
