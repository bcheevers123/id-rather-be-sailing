# Testing

## Running tests

```bash
# All pipeline tests
pytest

# With coverage
pytest --cov=pipeline --cov-report=term-missing

# Frontend tests
npm test

# Specific test file
pytest tests/pipeline/test_pdf_parser.py -v
```

## Test categories

### Pipeline unit tests (use fixtures — no live HTTP)

| File | Tests |
|---|---|
| `test_mca_source.py` | PDF URL discovery from saved HTML fixture |
| `test_pdf_parser.py` | Provider extraction from PDF fixtures (PST, FPFF, FRB) |
| `test_normalise.py` | Slug generation, name dedup, "not open to public" handling |
| `test_validate.py` | Schema validation pass/fail cases for all entity types |
| `test_freshness.py` | Freshness status logic for all thresholds |
| `test_change_detector.py` | Provider added, removed, price jump, zero-offerings anomaly |
| `test_adapters_arlo.py` | Arlo adapter against saved HTML fixture |
| `test_adapters_generic_html.py` | Fallback scraper against fixture |
| `test_generate.py` | Full pipeline orchestration with mocked HTTP |

### Frontend unit tests (Vitest)

| File | Tests |
|---|---|
| `search.test.ts` | Alias expansion, fuzzy matching, confusion note surfacing |
| `filters.test.ts` | All filter combinations, sort orders |
| `Calendar.test.tsx` | Event rendering, multi-day spans, empty state |

## Fixture policy

- Parser tests use saved files in `tests/pipeline/fixtures/`
- HTTP responses are mocked with `responses` library (never live)
- A small separate smoke test suite (`tests/smoke/`) may hit live URLs but is NOT run in CI

## Coverage target

Pipeline: ≥ 85% line coverage on `pipeline/` excluding `pipeline/adapters/` stubs.
