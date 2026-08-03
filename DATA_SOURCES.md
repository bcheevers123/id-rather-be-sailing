# Data Sources

## Layer A — Official MCA approval data

| Property | Value |
|---|---|
| Source | https://www.gov.uk/guidance/mca-approved-training-providers-atp |
| Format | Individual PDFs (one per course), text-based, parseable |
| Update cycle | Monthly |
| Last confirmed | 2026-07-16 |
| Parser | `pipeline/pdf_parser.py` using `pdfplumber` |

Each PDF contains: provider name, location (UK county or country), full address, telephone, email, website.

PDF URLs change monthly (date-stamped filenames). The pipeline always re-discovers them from the main page rather than hardcoding URLs.

## Layer B — Provider schedule data

Each provider's own website. See `PROVIDER_COVERAGE.md` for current adapter status per provider.

## Data not collected

- User data of any kind
- Private or login-required provider pages
- Third-party aggregator sites (unless clearly identified as the actual approved provider)
