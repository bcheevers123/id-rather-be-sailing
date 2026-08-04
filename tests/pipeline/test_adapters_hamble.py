from pathlib import Path
import responses

from pipeline.adapters.hamble import HambleAdapter, _parse_course_page
from pipeline.adapters.base import Offering

FIXTURE_PST = Path("tests/pipeline/fixtures/hamble_pst_page.html").read_text(encoding="utf-8")
FIXTURE_MFA = Path("tests/pipeline/fixtures/hamble_mfa_page.html").read_text(encoding="utf-8")

PROVIDER = {
    "id": "hamble-school-of-yachting",
    "official_name": "Hamble School of Yachting",
    "website": "https://www.hamble.co.uk/",
}

PST_URL = "https://www.hamble.co.uk/mca-stcw-courses/mca-stcw-personal-survival-techniques"
MFA_URL = "https://www.hamble.co.uk/mca-stcw-proficiency-in-medical-first-aid-on-board-ship"


def test_parse_pst_page_extracts_dates_from_options():
    offerings = _parse_course_page(
        FIXTURE_PST,
        source_url=PST_URL,
        course_id="pst",
        default_price=155.0,
        duration_days=1,
        provider=PROVIDER,
    )
    assert len(offerings) >= 5
    assert all(isinstance(o, Offering) for o in offerings)
    assert all(o.course_id == "pst" for o in offerings)
    assert all(o.start_date is not None for o in offerings)
    assert all(o.end_date is not None for o in offerings)
    assert all(o.price == 155.0 for o in offerings)
    assert all(o.currency == "GBP" for o in offerings)
    assert all(o.delivery_format == "in_person" for o in offerings)
    assert all(o.timezone == "Europe/London" for o in offerings)


def test_parse_pst_no_duplicate_dates():
    offerings = _parse_course_page(
        FIXTURE_PST,
        source_url=PST_URL,
        course_id="pst",
        default_price=155.0,
        duration_days=1,
        provider=PROVIDER,
    )
    dates = [o.start_date for o in offerings]
    assert len(dates) == len(set(dates))


def test_parse_mfa_page_extracts_date_ranges():
    offerings = _parse_course_page(
        FIXTURE_MFA,
        source_url=MFA_URL,
        course_id="mfa",
        default_price=515.0,
        duration_days=4,
        provider=PROVIDER,
    )
    assert len(offerings) >= 2
    for o in offerings:
        assert o.course_id == "mfa"
        assert o.start_date < o.end_date  # 4-day course, end after start
        assert o.price == 515.0
        assert o.duration_days == 4.0


def test_parse_offering_id_format():
    offerings = _parse_course_page(
        FIXTURE_PST,
        source_url=PST_URL,
        course_id="pst",
        default_price=155.0,
        duration_days=1,
        provider=PROVIDER,
    )
    for o in offerings:
        assert o.id.startswith("pst-hamble-")
        assert o.provider_id == "hamble-school-of-yachting"


@responses.activate
def test_http_error_returns_empty():
    responses.add(responses.GET, PST_URL, status=503)
    responses.add(responses.GET, MFA_URL, status=503)
    responses.add(
        responses.GET,
        "https://www.hamble.co.uk/mca-stcw-elementary-first-aid",
        status=503,
    )
    responses.add(
        responses.GET,
        "https://www.hamble.co.uk/mca-stcw-proficiency-in-medical-care-on-board-ship",
        status=503,
    )
    adapter = HambleAdapter()
    result = adapter.fetch(PROVIDER)
    assert result == []
