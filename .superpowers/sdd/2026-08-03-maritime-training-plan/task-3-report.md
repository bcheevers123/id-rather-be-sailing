# Task 3 Report: JSON schemas and validate module

## Status
**DONE**

## Commits
- `c6b90a6` feat: JSON schemas and validate module

## Test Summary
- **3 passed** in 0.13s
- Full suite: **3 passed**, **0 failed**
- All tests passing:
  - `test_valid_course_passes` ✓
  - `test_course_missing_required_field_fails` ✓
  - `test_validate_all_filters_invalid` ✓

## Implementation Summary

### Files Created
1. `tests/pipeline/test_validate.py` — Complete test suite with 3 test functions
2. `pipeline/schemas/course.schema.json` — Course validation schema
3. `pipeline/schemas/provider.schema.json` — Provider validation schema
4. `pipeline/schemas/approval.schema.json` — Approval validation schema
5. `pipeline/schemas/offering.schema.json` — Offering validation schema
6. `pipeline/schemas/retrieval_log.schema.json` — Retrieval log validation schema
7. `pipeline/schemas/coverage_report.schema.json` — Coverage report validation schema
8. `pipeline/validate.py` — Validation module with `validate_record()` and `validate_all()` functions

### Key Implementation Details
- **`validate_record(schema_name: str, record: dict) -> None`** — Validates a single record against a named schema; raises `jsonschema.ValidationError` on failure
- **`validate_all(schema_name: str, records: list[dict]) -> list[dict]`** — Filters valid records only; logs and discards invalid ones with `logger.error()`
- Schema caching via module-level `_schema_cache` dict prevents re-reading files on repeated calls
- All 6 schemas use JSON Schema draft-07 with strict validation (additionalProperties: false)
- All required fields and enum values match brief exactly for downstream task compatibility

### Minor Config Change
- Updated `pytest.ini` to add `pythonpath = .` for proper Python path resolution during test collection

## No Concerns
All implementation matches brief specifications exactly. Tests confirm validation works correctly.
