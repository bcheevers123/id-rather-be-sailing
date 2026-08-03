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
