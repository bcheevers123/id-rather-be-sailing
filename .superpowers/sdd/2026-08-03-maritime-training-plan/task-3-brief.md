# Task 3 Brief: JSON schemas and validate module

## Context

This is Task 3 of the "I'd Rather Be Sailing" implementation plan — a static React + Python pipeline for maritime training course discovery. The scaffold (Task 1) and documentation (Task 2) are complete on branch `feature/maritime-training`. You are implementing the JSON schema validation layer: 6 schema files and the `pipeline/validate.py` module.

## Working directory

`C:\Users\BarryCheevers\OneDrive - Anomali\Desktop\Fun\I'd Rather Be Sailing`

Branch: `feature/maritime-training`

Python venv: create if needed. `pip install -r requirements.txt` to install deps (jsonschema is in there).

## Files to create

- `pipeline/schemas/course.schema.json`
- `pipeline/schemas/provider.schema.json`
- `pipeline/schemas/approval.schema.json`
- `pipeline/schemas/offering.schema.json`
- `pipeline/schemas/retrieval_log.schema.json`
- `pipeline/schemas/coverage_report.schema.json`
- `pipeline/validate.py`
- `tests/pipeline/test_validate.py`

## Interfaces produced (exact signatures, used by Tasks 5-8)

```python
validate_record(schema_name: str, record: dict) -> None
# Raises jsonschema.ValidationError on failure

validate_all(schema_name: str, records: list[dict]) -> list[dict]
# Returns only valid records; logs and discards invalid ones
```

## Exact implementation

### tests/pipeline/test_validate.py

```python
import pytest
from pipeline.validate import validate_record, validate_all
from jsonschema import ValidationError

def test_valid_course_passes():
    record = {
        "id": "pst",
        "official_name": "Personal Survival Techniques",
        "abbreviation": "PST",
        "aliases": [],
        "category": "stcw_basic",
        "description": None,
        "confusion_note": None,
        "source_pdf_url": "https://example.com/pst.pdf",
        "source_updated_date": "2026-07-16",
        "provider_count": 0,
        "earliest_known_date": None,
        "lowest_known_price_gbp": None,
    }
    validate_record("course", record)  # should not raise

def test_course_missing_required_field_fails():
    with pytest.raises(ValidationError):
        validate_record("course", {"id": "pst"})  # missing official_name etc.

def test_validate_all_filters_invalid(capsys):
    records = [
        {
            "id": "pst",
            "official_name": "PST",
            "abbreviation": "PST",
            "aliases": [],
            "category": "stcw_basic",
            "description": None,
            "confusion_note": None,
            "source_pdf_url": "https://example.com/pst.pdf",
            "source_updated_date": "2026-07-16",
            "provider_count": 0,
            "earliest_known_date": None,
            "lowest_known_price_gbp": None,
        },
        {"id": "bad"},  # invalid
    ]
    valid = validate_all("course", records)
    assert len(valid) == 1
    assert valid[0]["id"] == "pst"
```

### pipeline/schemas/course.schema.json

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["id","official_name","abbreviation","aliases","category","description","confusion_note","source_pdf_url","source_updated_date","provider_count","earliest_known_date","lowest_known_price_gbp"],
  "additionalProperties": false,
  "properties": {
    "id": {"type": "string", "pattern": "^[a-z0-9-]+$"},
    "official_name": {"type": "string", "minLength": 1},
    "abbreviation": {"type": ["string","null"]},
    "aliases": {"type": "array", "items": {"type": "string"}},
    "category": {"type": "string", "enum": ["stcw_basic","stcw_advanced","stcw_refresher","stcw_tanker","stcw_igf","stcw_helm","stcw_ecdis_naest","gmdss","high_voltage","security","deck_yacht","sv_engineering","engineering_other","polar","workboat","other"]},
    "description": {"type": ["string","null"]},
    "confusion_note": {"type": ["string","null"]},
    "source_pdf_url": {"type": "string", "format": "uri"},
    "source_updated_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
    "provider_count": {"type": "integer", "minimum": 0},
    "earliest_known_date": {"type": ["string","null"]},
    "lowest_known_price_gbp": {"type": ["number","null"], "minimum": 0}
  }
}
```

### pipeline/schemas/provider.schema.json

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["id","official_name","alt_names","address","city","region","country","postcode","lat","lng","website","email","telephone","not_open_to_public"],
  "additionalProperties": false,
  "properties": {
    "id": {"type": "string", "pattern": "^[a-z0-9-]+$"},
    "official_name": {"type": "string", "minLength": 1},
    "alt_names": {"type": "array", "items": {"type": "string"}},
    "address": {"type": ["string","null"]},
    "city": {"type": ["string","null"]},
    "region": {"type": ["string","null"]},
    "country": {"type": ["string","null"]},
    "postcode": {"type": ["string","null"]},
    "lat": {"type": ["number","null"]},
    "lng": {"type": ["number","null"]},
    "website": {"type": ["string","null"]},
    "email": {"type": ["string","null"]},
    "telephone": {"type": ["string","null"]},
    "not_open_to_public": {"type": "boolean"}
  }
}
```

### pipeline/schemas/approval.schema.json

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["course_id","provider_id","source_pdf_url","source_updated_date","status","first_seen","last_seen","not_open_to_public"],
  "additionalProperties": false,
  "properties": {
    "course_id": {"type": "string"},
    "provider_id": {"type": "string"},
    "source_pdf_url": {"type": "string", "format": "uri"},
    "source_updated_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
    "status": {"type": "string", "enum": ["active","removed"]},
    "first_seen": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
    "last_seen": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
    "not_open_to_public": {"type": "boolean"}
  }
}
```

### pipeline/schemas/offering.schema.json

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["id","course_id","provider_id","start_date","end_date","timezone","duration_days","price","currency","vat_included","delivery_format","availability","booking_url","source_url","last_verified","freshness_status"],
  "additionalProperties": false,
  "properties": {
    "id": {"type": "string"},
    "course_id": {"type": "string"},
    "provider_id": {"type": "string"},
    "start_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
    "end_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
    "timezone": {"type": "string"},
    "duration_days": {"type": ["number","null"]},
    "price": {"type": ["number","null"], "minimum": 0},
    "currency": {"type": ["string","null"]},
    "vat_included": {"type": ["boolean","null"]},
    "delivery_format": {"type": "string", "enum": ["in_person","blended","online","unknown"]},
    "availability": {"type": ["string","null"]},
    "booking_url": {"type": ["string","null"]},
    "source_url": {"type": "string"},
    "last_verified": {"type": "string"},
    "freshness_status": {"type": "string", "enum": ["verified","recently_checked","stale","source_unavailable","no_public_schedule"]}
  }
}
```

### pipeline/schemas/retrieval_log.schema.json

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["source_url","retrieved_at","http_status","content_hash","parser_id","parse_result","error_detail","offerings_found","previous_good_result_at"],
  "additionalProperties": false,
  "properties": {
    "source_url": {"type": "string"},
    "retrieved_at": {"type": "string"},
    "http_status": {"type": ["integer","null"]},
    "content_hash": {"type": ["string","null"]},
    "parser_id": {"type": "string"},
    "parse_result": {"type": "string", "enum": ["ok","failed","no_data"]},
    "error_detail": {"type": ["string","null"]},
    "offerings_found": {"type": "integer", "minimum": 0},
    "previous_good_result_at": {"type": ["string","null"]}
  }
}
```

### pipeline/schemas/coverage_report.schema.json

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["generated_at","total_courses","total_providers","total_approvals","providers_with_dates","providers_with_prices","providers_requiring_manual_review","providers_blocking_automated_collection","providers_no_public_schedule","last_successful_full_refresh","parse_failures"],
  "additionalProperties": false,
  "properties": {
    "generated_at": {"type": "string"},
    "total_courses": {"type": "integer"},
    "total_providers": {"type": "integer"},
    "total_approvals": {"type": "integer"},
    "providers_with_dates": {"type": "integer"},
    "providers_with_prices": {"type": "integer"},
    "providers_requiring_manual_review": {"type": "integer"},
    "providers_blocking_automated_collection": {"type": "integer"},
    "providers_no_public_schedule": {"type": "integer"},
    "last_successful_full_refresh": {"type": ["string","null"]},
    "parse_failures": {"type": "array", "items": {"type": "object","required": ["provider_id","reason"],"properties": {"provider_id": {"type": "string"},"reason": {"type": "string"}}}}
  }
}
```

### pipeline/validate.py

```python
import json
import logging
from pathlib import Path

import jsonschema

_SCHEMA_DIR = Path(__file__).parent / "schemas"
_schema_cache: dict[str, dict] = {}

logger = logging.getLogger(__name__)


def _load_schema(name: str) -> dict:
    if name not in _schema_cache:
        path = _SCHEMA_DIR / f"{name}.schema.json"
        with path.open() as f:
            _schema_cache[name] = json.load(f)
    return _schema_cache[name]


def validate_record(schema_name: str, record: dict) -> None:
    """Validate record against named schema. Raises jsonschema.ValidationError on failure."""
    schema = _load_schema(schema_name)
    jsonschema.validate(record, schema)


def validate_all(schema_name: str, records: list[dict]) -> list[dict]:
    """Return only valid records; log and discard invalid ones."""
    valid = []
    for record in records:
        try:
            validate_record(schema_name, record)
            valid.append(record)
        except jsonschema.ValidationError as e:
            identifier = record.get("id") or record.get("source_url") or "(unknown)"
            logger.error("Schema validation failed for %s (%s): %s", schema_name, identifier, e.message)
    return valid
```

## Steps

1. Write `tests/pipeline/test_validate.py` with the exact test code above
2. Run `pytest tests/pipeline/test_validate.py -v` — expect ImportError/ModuleNotFoundError
3. Create `pipeline/schemas/` directory and all 6 schema JSON files with exact content above
4. Create `pipeline/validate.py` with exact content above
5. Run `pytest tests/pipeline/test_validate.py -v` — expect 3 tests pass
6. Run full suite: `pytest` — should still be zero failures
7. Commit:
   ```bash
   git add pipeline/schemas/ pipeline/validate.py tests/pipeline/test_validate.py
   git commit -m "feat: JSON schemas and validate module"
   ```

## Global constraints

- Use the exact field names, types, and enum values shown — later tasks depend on them
- No fabricated data in test fixtures — use the exact record shown
- `validate_all` logs but never raises — it returns the valid subset
- `_schema_cache` is module-level dict to avoid re-reading files on every call

## Report file

Write your report to: `.superpowers/sdd/2026-08-03-maritime-training-plan/task-3-report.md`

Return only:
- Status: DONE / DONE_WITH_CONCERNS / BLOCKED
- Commits made (git hashes)
- Test summary (N passed, N failed)
- Any concerns
