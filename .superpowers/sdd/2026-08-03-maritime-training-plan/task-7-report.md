# Task 7 Report: BaseAdapter, Offering dataclass, Arlo adapter

## Status

COMPLETE

## Commit

`21c9f0d` — feat: BaseAdapter, Offering dataclass, Arlo adapter

## Test Summary

```
30 passed, 7 warnings in 5.94s
```

New tests (3/3):
- `test_arlo_extracts_offerings` — PASSED (17 offerings found, >= 5 required)
- `test_arlo_offering_has_required_fields` — PASSED
- `test_arlo_http_error_returns_empty` — PASSED

All 27 prior tests continue to pass.

## Files Created

- `pipeline/adapters/base.py` — `Offering` dataclass (16 fields) + `BaseAdapter` ABC
- `pipeline/adapters/arlo.py` — `ArloAdapter` implementation
- `tests/pipeline/fixtures/arlo_msa_course_page.html` — live MSA page (224,994 chars, fetched 2026-08-03)
- `tests/pipeline/test_adapters_arlo.py` — 3 tests

## Fixture Structure — Key Findings

The brief's suggested selectors (`li.session`, `tr.session`, `div.upcoming`) do NOT appear in the real page. The actual structure is:

- Each session is wrapped in a `div` with class `event m-b-10`
- Start date: `span.arlo-start-date` — text like "10 August 2026"
- End date: `span.arlo-end-date` — text like "14 August 2026"
- Price: `span.amount` — text like "£875.00" (UTF-8 £, U+00A3)
- VAT status: `span.arlo-price-tax` — text "incl. VAT"
- Availability: `span.arlo-places-remaining` — text "5 places remaining"
- Booking link: `<a href="https://maritimeskillsacademy.arlo.co/dv/register?sgid=...">Register</a>`

The fixture contains 17 session events (Aug 2026 – Aug 2027), all priced at £875.00 incl. VAT.

There was NO deduplication issue — each `div.event` is a distinct session (the 34 `arlo-start-date` spans visible in a broad search are because each event renders twice inside its container for desktop/mobile layout, but contained within a single `div.event`).

## Parser Approach

The adapter uses `div.event` containers as the iteration unit, then reads the Arlo-specific span classes directly. Date parsing delegates to `python-dateutil`. The `£` sign is correctly handled at U+00A3 in the regex. `fetch()` catches all exceptions at both HTTP and parse layers and returns `[]`.
