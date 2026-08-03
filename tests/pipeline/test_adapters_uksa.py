from pathlib import Path
import responses
from pipeline.adapters.uksa import UKSAAdapter

FIXTURE = Path("tests/pipeline/fixtures/uksa_course_page.html").read_text(encoding="utf-8")
PROVIDER = {"id": "united-kingdom-sailing-academy-uksa", "official_name": "UKSA", "website": "https://uksa.org/"}


@responses.activate
def test_uksa_fetch_returns_list():
    responses.add(responses.GET,
        "https://www.uksa.org/courses/mca-personal-survival-techniques-pst",
        body=FIXTURE, status=200)
    adapter = UKSAAdapter("pst")
    result = adapter.fetch(PROVIDER)
    assert isinstance(result, list)


@responses.activate
def test_uksa_http_error_returns_empty():
    responses.add(responses.GET,
        "https://www.uksa.org/courses/mca-personal-survival-techniques-pst",
        status=404)
    adapter = UKSAAdapter("pst")
    result = adapter.fetch(PROVIDER)
    assert result == []
