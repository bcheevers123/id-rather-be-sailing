# I'd Rather Be Sailing — Design Specification

**Date:** 2026-08-03  
**Version:** 1.0  
**Repo:** https://github.com/bcheevers123/id-rather-be-sailing  
**Hosting:** GitHub Pages + GitHub Actions  

---

## 1. Product overview

A public web application that helps maritime professionals find MCA (Maritime and Coastguard Agency) approved training courses, the approved centres offering them, and upcoming dates and prices where that information is publicly available.

No accounts. No invented data. No scraping in the browser. Honest and explicit about what is and isn't known.

**MCA** — the UK government body that approves training centres and certifies seafarers.  
**STCW** — Standards of Training, Certification and Watchkeeping; the international framework governing most mandatory seafarer training.

---

## 2. What the application does and does not guarantee

**Does:**
- Show every MCA-approved course found in the official source
- Show every approved training centre for each course
- Show upcoming dates and prices where they are publicly available and reliably parseable
- Clearly attribute every piece of data to its source and timestamp

**Does not:**
- Guarantee that every provider's schedule is current (it is only as fresh as the last successful pipeline run)
- Guarantee that every provider has upcoming dates (many do not publish schedules online)
- Fabricate, estimate or infer any date, price, duration or availability
- Replace direct contact with a provider before booking

---

## 3. The two data layers

### Layer A — Official approval data
**Source:** MCA/GOV.UK PDF documents  
**URL:** https://www.gov.uk/guidance/mca-approved-training-providers-atp  
**Update cycle:** Monthly  
**Establishes:** Which courses exist, their official names and categories, which providers are approved for each, provider contact details, the source document, and when it was last updated.

### Layer B — Provider offering data
**Source:** Each approved provider's own website  
**Update cycle:** Daily pipeline run  
**Establishes:** Upcoming dates, prices, currency, duration, delivery format, availability, booking URL.  

Layer A takes precedence. A provider is never removed from results because Layer B failed.

---

## 4. Architecture

### Chosen: Option A — Fully static + GitHub Actions

```
Repository: bcheevers123/id-rather-be-sailing
│
├── pipeline/                  Python data pipeline
│   ├── mca_source.py          Discover & download MCA PDFs
│   ├── pdf_parser.py          Parse provider tables from PDFs
│   ├── normalise.py           Clean, deduplicate, validate
│   ├── adapters/              Per-provider schedule adapters
│   │   ├── base.py            Common interface
│   │   ├── arlo.py            Arlo platform (covers multiple providers)
│   │   ├── generic_html.py    Fallback HTML scraper
│   │   └── [provider].py      Provider-specific adapters
│   ├── generate.py            Write static JSON to src/data/
│   ├── report.py              Write coverage_report.json
│   └── schemas/               JSON Schema files for validation
│
├── src/                       React + Vite + TypeScript frontend
│   ├── data/                  Pre-generated JSON (committed, updated by pipeline)
│   ├── components/
│   ├── views/
│   │   ├── Catalogue.tsx      Course catalogue
│   │   ├── CourseResults.tsx  Approved providers for a course
│   │   └── Calendar.tsx       Rolling calendar
│   └── lib/
│       ├── search.ts          Fuse.js alias-aware search
│       └── filters.ts         Filter/sort logic
│
└── .github/workflows/
    ├── refresh.yml            Daily cron: run pipeline, commit JSON, trigger deploy
    └── deploy.yml             Build and deploy to GitHub Pages
```

**Data flow:**
1. GitHub Actions cron runs the Python pipeline daily
2. Pipeline discovers current PDF URLs from the MCA page (URLs change monthly — never hardcoded)
3. Pipeline downloads and parses all PDFs, extracts provider-course records
4. Pipeline visits each provider website via per-provider adapters, extracts dates/prices
5. Pipeline validates all records against JSON Schema, rejects malformed data
6. Pipeline writes updated JSON to `src/data/`, commits, and pushes
7. Push triggers the deploy workflow, which builds the React app and publishes to GitHub Pages
8. Users load the React SPA and fetch static JSON directly — no backend

**Why this is the right choice:**
- £0 hosting cost
- No servers to operate
- Data pipeline is independent of the frontend
- Safe failure mode: stale JSON is retained from the last good run
- All scraping happens server-side (in Actions), never in the user's browser
- Satisfies all requirements: PDF parsing, provider scraping, scheduled refresh, failure reporting, safe publication

**What would trigger an upgrade:** A provider requires JavaScript execution to expose dates (needs headless browser, slow in Actions); total JSON exceeds ~50 MB; user personalisation features are added.

---

## 5. Data model

All data lives in `src/data/` as static JSON files.

### 5.1 courses.json
```
{
  "id": "pst",                          // stable slug
  "official_name": "Personal Survival Techniques",
  "abbreviation": "PST",
  "aliases": ["Basic Safety Training PST"],
  "category": "stcw_basic",
  "description": "...",                 // concise interface summary; not fabricated
  "source_pdf_url": "https://assets.publishing.service.gov.uk/media/.../PST_16.07.2026.pdf",
  "source_updated_date": "2026-07-16",
  "provider_count": 47,
  "earliest_known_date": "2026-08-10",  // null if unknown
  "lowest_known_price_gbp": 160.0       // null if unknown
}
```

### 5.2 providers.json
```
{
  "id": "maritime-skills-academy-dover",
  "official_name": "Maritime Skills Academy (Dover) part of Viking Maritime Group",
  "alt_names": ["Viking MSA", "MSA Dover"],
  "address": "Viking House, Beechwood Business Park, Menzies Road, Dover, Kent CT16 2FG",
  "city": "Dover",
  "region": "Kent",
  "country": "GB",
  "postcode": "CT16 2FG",
  "lat": null,
  "lng": null,
  "website": "https://www.maritimeskillsacademy.com/",
  "email": "info@vikingmsa.com",
  "telephone": "+44 3003 038393"
}
```

### 5.3 approvals.json
```
{
  "course_id": "pst",
  "provider_id": "maritime-skills-academy-dover",
  "source_pdf_url": "https://assets.publishing.service.gov.uk/media/.../PST_16.07.2026.pdf",
  "source_updated_date": "2026-07-16",
  "status": "active",                   // active | removed
  "first_seen": "2026-08-03",
  "last_seen": "2026-08-03",
  "not_open_to_public": false
}
```

### 5.4 offerings.json
```
{
  "id": "pst-msa-dover-2026-08-10",
  "course_id": "pst",
  "provider_id": "maritime-skills-academy-dover",
  "start_date": "2026-08-10",
  "end_date": "2026-08-14",
  "timezone": "Europe/London",
  "duration_days": 5,
  "price": 875.00,
  "currency": "GBP",
  "vat_included": true,
  "delivery_format": "in_person",       // in_person | blended | online | unknown
  "availability": null,                 // null if not published
  "booking_url": "https://maritimeskillsacademy.arlo.co/...",
  "source_url": "https://www.maritimeskillsacademy.com/courses/stcw-basic-safety-training",
  "last_verified": "2026-08-03T06:00:00Z",
  "freshness_status": "verified"        // verified | recently_checked | stale | source_unavailable | no_public_schedule
}
```

### 5.5 retrieval_log.json
```
{
  "source_url": "https://www.maritimeskillsacademy.com/courses/stcw-pst",
  "retrieved_at": "2026-08-03T06:12:34Z",
  "http_status": 200,
  "content_hash": "sha256:abc123...",
  "parser_id": "arlo_v1",
  "parse_result": "ok",                 // ok | failed | no_data
  "error_detail": null,
  "offerings_found": 17,
  "previous_good_result_at": "2026-08-02T06:11:22Z"
}
```

### 5.6 coverage_report.json
```
{
  "generated_at": "2026-08-03T06:45:00Z",
  "total_courses": 75,
  "total_providers": 312,
  "total_approvals": 1847,
  "providers_with_dates": 48,
  "providers_with_prices": 41,
  "providers_requiring_manual_review": 12,
  "providers_blocking_automated_collection": 3,
  "providers_no_public_schedule": 189,
  "last_successful_full_refresh": "2026-08-03T06:44:58Z",
  "parse_failures": [
    {"provider_id": "...", "reason": "..."}
  ]
}
```

**Schema validation:** Every entity has a corresponding JSON Schema in `pipeline/schemas/`. The pipeline halts and logs an error for any record that fails validation rather than passing malformed data to the frontend.

---

## 6. Course categories

| Category ID | Display name | Examples |
|---|---|---|
| `stcw_basic` | STCW Basic Training | PST, FPFF, EFA, PSSR |
| `stcw_advanced` | STCW Advanced Training | AFF, PSCRB, MFA, Medical Care, FRB, Yacht-Restricted PSCRB |
| `stcw_refresher` | Updating STCW Training | UPST, UFPFF, UAFF, UPSCRB, UFRB, UMC, Updating Yacht-Restricted PSCRB |
| `stcw_tanker` | Tanker Training | Basic/Advanced Oil, Chemical, Gas; Tanker Fire Fighting |
| `stcw_igf` | IGF Code Training (Alternative Fuels) | Basic/Advanced IGF; Ammonia, Methanol, Hydrogen variants |
| `stcw_helm` | HELM — Leadership & Management | HELM Operational, HELM Management |
| `stcw_ecdis_naest` | ECDIS & NAEST | ECDIS, NAEST-O, NAEST-M |
| `gmdss` | GMDSS / Radio | GOC, ROC, LRC |
| `high_voltage` | High Voltage | HV Operational, HV Management |
| `security` | Security Training | Security Awareness, DSD, SSO, CSO |
| `deck_yacht` | Deck Yacht Modules | OOW GSK, OOW Nav/Rad, Master B&L, Master Nav/Rad, Master S&M, Stability |
| `sv_engineering` | Small Vessel Engineering Modules | SV Workshop Skills, Aux 1 & 2, Marine Diesel, etc. |
| `engineering_other` | Non-STCW Engineering | GES I&II, AEC1, AEC2, AEPC1 |
| `polar` | Polar Waters Training | Basic Polar, Advanced Polar |
| `workboat` | Workboat Courses | Non-STCW Nav/Radar, Stability (WBC3) |
| `other` | Other MCA-approved Training | EDH, YRC, Helideck, CMHB, Passenger Safety, Safety Officer, MASS, etc. |

---

## 7. Search and alias system

A controlled alias table (`pipeline/aliases.json`) maps abbreviations and common names to canonical course IDs. This is maintained manually — not generated by an LLM at runtime.

**Confusion prevention:** Courses that are frequently confused have a `confusion_note` field in courses.json, shown as a disambiguation banner in the UI:

- PST (initial) vs UPST (refresher/update)
- PSCRB vs PSCRB-R (yacht-restricted variant)
- HELM-O (Operational) vs HELM-M (Management)
- Basic IGF vs Advanced IGF
- Basic Oil Tanker vs Advanced Oil Tanker

**Frontend search:** Fuse.js with threshold 0.3, searching against `official_name`, `abbreviation`, and all `aliases[]`. Matched courses include confusion notes where applicable.

---

## 8. Frontend views

### 8.1 Course catalogue (`/`)
- Search bar (alias-aware, fuzzy)
- Category accordion/tabs
- Course cards: name, abbreviation, plain-English summary, # providers, earliest date, lowest price, freshness badge
- Filter panel: category, country, has upcoming date, has public price
- URL-encoded filter state

### 8.2 Course results page (`/course/:id`)
- Course header: official name, abbreviation, description, source attribution
- Disambiguation banner if confusion note exists
- Provider results list, each showing all fields from spec §4 of the instruction document
- Providers without dates shown with "No public dates found — contact provider"
- Filter: country, region, max price, currency, delivery format, has upcoming date
- Sort: earliest date, lowest price, provider name, most recently verified
- Freshness badge per provider result

### 8.3 Rolling calendar (`/calendar`)
- Default: next 3 months
- Month view (desktop), agenda/timeline view (mobile default)
- Navigate forward/backward by month
- Filter: course, provider, country
- Each event: abbreviation, provider, city, price if known, booking link
- Multi-day events span correctly
- Events without confirmed dates are excluded
- URL-encoded filter state

---

## 9. Data freshness policy

| Data type | Freshness threshold |
|---|---|
| MCA approval data (PDFs) | Stale if >32 days (slightly longer than the monthly update cycle) |
| Provider schedule data | Verified: <24h; Recently checked: 1–7 days; Stale: >7 days |
| Past course dates | Removed from offerings on next pipeline run; moved to archived_offerings.json |
| Failed refresh | Last known good data retained; marked stale with timestamp |

**Stale-data safety:** A failed refresh never replaces valid data with empty data. The pipeline writes new JSON only if validation passes. If validation fails, the previous JSON is retained and the failure is logged.

---

## 10. Failure handling policy

| Failure scenario | Handling |
|---|---|
| MCA page unreachable | Abort pipeline run; retain previous JSON; log alert |
| Individual PDF download fails | Skip that course's provider update; log; previous data retained |
| Provider site unreachable | Mark offerings `source_unavailable`; retain last good data |
| Provider blocks automated access | Mark `no_public_schedule`; log reason in coverage report |
| JSON Schema validation fails | Reject record; log details; do not publish |
| Parser returns zero offerings (anomaly) | Flag as suspicious change; retain previous; require human review |
| Provider added in PDF not in previous data | Log as new provider; add to JSON; email or Actions notification |
| Provider removed from PDF | Mark approval `status: removed`; retain provider card with notice |

---

## 11. Scraping policy summary

- Check for structured data or API before scraping HTML
- Review `robots.txt` for every provider site
- Use descriptive User-Agent: `Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; +https://github.com/bcheevers123/id-rather-be-sailing)`
- Rate limit: minimum 2-second delay between requests per domain
- Cache: store `ETag`/`Last-Modified` headers; use conditional requests
- Do not bypass authentication, CAPTCHAs or anti-bot measures
- Do not scrape login-required pages
- If `robots.txt` disallows: mark provider as `no_public_schedule`; never attempt to scrape

Full policy: `SCRAPING_POLICY.md`

---

## 12. MVP scope

### In scope
- All ~75 MCA-approved courses from the official source
- All approved providers from all course PDFs
- Daily pipeline refresh via GitHub Actions
- Course catalogue with search, filter, sort
- Course results page per course
- Rolling calendar
- Arlo platform adapter (covers multiple providers)
- At least 3 further provider-specific adapters
- Coverage report
- All required documentation files
- GitHub Pages deployment
- WCAG 2.2 AA accessibility

### Explicit non-goals (MVP)
- User accounts, saved searches, favourites, alerts
- Email notifications
- Distance-based filtering (may add later if a free geocoding solution is viable)
- Currency conversion
- Booking directly within the app
- Mobile app
- Paid infrastructure
- Real-time data (daily is sufficient)

---

## 13. User journeys

**Journey 1 — Finding a specific course:**
1. Arrive at catalogue, type "PST" in search
2. See PST result with disambiguation note about UPST (refresher)
3. Click PST → results page
4. See 47 providers; filter to UK, has upcoming date
5. Sort by earliest date
6. Click booking link for Maritime Skills Academy Dover → go to provider site

**Journey 2 — Browse by category:**
1. Arrive at catalogue, open "STCW Basic Training" accordion
2. Browse all 4 basic courses with provider counts and earliest dates
3. Select Elementary First Aid → results page

**Journey 3 — Calendar view:**
1. Navigate to calendar
2. See all upcoming dates for next 3 months
3. Filter to course = FPFF
4. See which providers have dates this month; click event for booking link

---

## 14. Testing requirements

Coverage from the instruction document, mapped to test types:

| Area | Type |
|---|---|
| PDF parsing, provider extraction | Unit tests with PDF fixtures |
| Provider normalisation | Unit tests |
| Alias matching, confusion prevention | Unit tests |
| Date parsing, multi-day, timezones | Unit tests |
| Currency / VAT parsing | Unit tests |
| Missing prices / dates handling | Unit tests |
| Stale data retention on failure | Unit tests |
| Schema validation | Unit tests |
| Duplicate offering detection | Unit tests |
| Past-date archival | Unit tests |
| Change detection (added/removed provider) | Unit tests |
| Arlo adapter | Unit tests with HTTP fixtures |
| Search | Unit tests |
| Filter / sort | Unit tests |
| Calendar rendering | Component tests |
| Mobile layouts | Playwright / manual |
| Accessibility | axe-core + manual |
| Broken source link detection | Integration test |

Parser fixture tests use stored response files. They do not depend on live external sites. A small set of smoke integration tests may hit live URLs but are not run in the daily pipeline.

---

## 15. Security and privacy

- No personal user data collected
- No cookies (except technically necessary, e.g. session for GitHub Pages custom domain HTTPS — none planned)
- No authentication
- All scraped content treated as untrusted; sanitised before rendering
- React's default JSX escaping prevents XSS; no `dangerouslySetInnerHTML`
- Source URLs validated against allowlist before rendering as links
- JSON Schema validation prevents malformed data reaching the frontend
- Repository secrets (e.g. GitHub token for Actions commits) stored as GitHub Actions secrets; never committed
- `CODEOWNERS` or branch protection prevents accidental secret commits

---

## 16. Required documentation files

All to be created and maintained in the repository root:

- `README.md`
- `PRODUCT_REQUIREMENTS.md`
- `ARCHITECTURE.md`
- `DATA_SOURCES.md`
- `DATA_MODEL.md`
- `SCRAPING_POLICY.md`
- `PROVIDER_COVERAGE.md`
- `DEPLOYMENT.md`
- `OPERATIONS.md`
- `TESTING.md`

---

## 17. Acceptance criteria (Phase 2 vertical slice)

- [ ] Pipeline successfully fetches the MCA page and discovers all current PDF URLs without hardcoding them
- [ ] Pipeline parses at least 3 course PDFs and produces valid courses.json, providers.json, approvals.json
- [ ] Pipeline fetches Maritime Skills Academy (Arlo) and produces valid offerings.json with upcoming dates and prices
- [ ] Pipeline produces coverage_report.json
- [ ] Frontend displays the course catalogue with all parsed courses
- [ ] Course results page shows all approved providers for a selected course
- [ ] Providers with no scraped dates show "No public dates found — contact provider"
- [ ] Rolling calendar shows known upcoming dates
- [ ] Search finds PST by typing "pst", "personal survival", or "basic safety"
- [ ] PST and UPST are not merged; confusion note is shown
- [ ] Freshness status is visible on every provider result
- [ ] All data is attributed to its source with a "last checked" timestamp
- [ ] GitHub Actions workflow runs the pipeline on schedule and deploys the result
- [ ] Site passes axe-core accessibility audit with zero critical violations
- [ ] No scraping occurs in the user's browser

---

*End of design specification.*
