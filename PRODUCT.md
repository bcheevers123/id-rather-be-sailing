# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**Primary:** Maritime professionals — seafarers, officers, and crew who need to find, book, or renew MCA-approved certificates (STCW Basic Safety, GMDSS, Advanced FF, PSCRB, HELM, tanker endorsements, etc.). They know what certificate they need; they want to find the nearest approved centre with a date that works and a visible price.

**Secondary:** Recreational sailors — RYA/MCA students looking for safety courses (PST, EFA, PSSR, FPFF) near them before a sailing season or trip.

## Product Purpose

A static, always-current directory of every MCA-approved training course and centre in the UK. The site layers live schedule data (dates and prices scraped daily from provider websites) on top of the official MCA approved training providers list, so users can go from "I need my PST renewed" to "here's a date at a centre near me, here's the price, here's the booking link" in one visit.

## Positioning

The MCA publishes a trusted list of approved providers as PDFs on gov.uk. This site uses that list as its ground truth for approval status — if a centre is on the gov.uk PDF, it is approved; if it is not, it is not shown. On top of that authoritative base, the site adds what the PDF cannot: upcoming dates, prices, and booking links scraped from provider websites and refreshed daily via GitHub Actions. No login, no ads, no invented data.

## Operating Context

- Users arrive knowing their certificate target (e.g. "PST renewal", "FPFF", "GMDSS GOC")
- They filter by location, format, price, and availability
- Booking happens off-site at the provider — this is a finder, not a booking platform
- Data freshness matters: stale dates erode trust; the freshness badges are load-bearing UI
- Used on desktop and mobile; maritime context means potentially poor connectivity ashore

## Capabilities and Constraints

- Fully static: React SPA on GitHub Pages, Python pipeline runs as daily GitHub Actions cron
- No backend, no database, no user accounts, no cookies beyond technical necessity
- Approval data sourced exclusively from gov.uk MCA PDFs — authoritative, not scraped from provider sites
- Schedule data (dates, prices, booking URLs) scraped from provider websites with 2s inter-request delay, robots.txt respect, and graceful fallback to "no public schedule"
- All scraped URLs validated (http/https only) before rendering as links
- No fabricated data — ever. If a date or price is unknown, it is absent, not invented
- WCAG 2.2 AA accessibility required

## Brand Commitments

Name: **I'd Rather Be Sailing** — irreverent, human, not corporate. The tool is useful for a serious professional task but the name signals it's made by someone who'd rather be on the water.

## Evidence on Hand

- MCA approved training provider PDFs (gov.uk) — ground truth for course and provider list
- 74 courses, 641 providers, 633 approvals in current pipeline output
- 17 live offerings currently (Maritime Skills Academy via Arlo adapter); more providers being added

## Product Principles

1. **Authoritative source, live layer** — approval status comes only from gov.uk; schedule data is a live layer on top, clearly distinguished
2. **No invented data** — absent information is shown as absent, never fabricated or inferred
3. **Freshness is visible** — users must be able to tell how current the schedule data is at a glance
4. **Finder, not booker** — this site gets users to the right centre; booking happens at the provider
5. **Works offline-tolerant** — static delivery, fast first load, graceful degradation when provider data is stale

## Accessibility & Inclusion

WCAG 2.2 AA required throughout. Focus rings, ARIA labels, role attributes, and keyboard navigation are mandatory, not optional.
