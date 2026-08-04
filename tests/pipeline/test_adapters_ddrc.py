from pathlib import Path
import responses

from pipeline.adapters.ddrc import DDRCAdapter, _parse_course_page, _compute_end_date
from pipeline.adapters.base import Offering

FIXTURE_MFA = Path("tests/pipeline/fixtures/ddrc_mfa_page.html").read_text(encoding="utf-8")

PROVIDER = {
    "id": "ddrc-professional-services",
    "official_name": "DDRC Healthcare",
    "website": "http://www.ddrc.org/",
}

MFA_URL = "https://www.ddrc.org/training/courses/11-stcw-mca-proficiency-in-medical-first-aid/region-UK/"


def test_parse_mfa_page_extracts_offerings():
    offerings = _parse_course_page(
        FIXTURE_MFA,
        source_url=MFA_URL,
        course_id="mfa",
        duration_days=4,
        provider=PROVIDER,
    )
    assert len(offerings) >= 3
    assert all(isinstance(o, Offering) for o in offerings)


def test_parse_mfa_fields():
    offerings = _parse_course_page(
        FIXTURE_MFA,
        source_url=MFA_URL,
        course_id="mfa",
        duration_days=4,
        provider=PROVIDER,
    )
    for o in offerings:
        assert o.course_id == "mfa"
        assert o.provider_id == "ddrc-professional-services"
        assert o.currency == "GBP"
        assert o.price == 575.0
        assert o.vat_included is True
        assert o.delivery_format == "in_person"
        assert o.timezone == "Europe/London"
        assert o.duration_days == 4.0
        assert o.start_date < o.end_date


def test_parse_mfa_booking_urls():
    offerings = _parse_course_page(
        FIXTURE_MFA,
        source_url=MFA_URL,
        course_id="mfa",
        duration_days=4,
        provider=PROVIDER,
    )
    for o in offerings:
        assert o.booking_url is not None
        assert "arlo.co" in o.booking_url


def test_parse_no_duplicate_dates():
    offerings = _parse_course_page(
        FIXTURE_MFA,
        source_url=MFA_URL,
        course_id="mfa",
        duration_days=4,
        provider=PROVIDER,
    )
    dates = [o.start_date for o in offerings]
    assert len(dates) == len(set(dates))


def test_offering_id_format():
    offerings = _parse_course_page(
        FIXTURE_MFA,
        source_url=MFA_URL,
        course_id="mfa",
        duration_days=4,
        provider=PROVIDER,
    )
    for o in offerings:
        assert o.id.startswith("mfa-ddrc-")


def test_compute_end_date_multi_day():
    assert _compute_end_date("2026-08-24", 4) == "2026-08-27"


def test_compute_end_date_single_day():
    assert _compute_end_date("2026-08-24", 1) == "2026-08-24"


def test_compute_end_date_none_duration():
    assert _compute_end_date("2026-08-24", None) == "2026-08-24"


@responses.activate
def test_http_error_returns_empty():
    for url in [
        MFA_URL,
        "https://www.ddrc.org/training/courses/12-stcw-mca-certificate-of-proficiency-in-medical-care/region-UK/",
        "https://www.ddrc.org/training/courses/60-stcw-mca-elementary-first-aid/region-UK/",
    ]:
        responses.add(responses.GET, url, status=503)
    adapter = DDRCAdapter()
    result = adapter.fetch(PROVIDER)
    assert result == []
