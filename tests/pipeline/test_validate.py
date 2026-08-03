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
