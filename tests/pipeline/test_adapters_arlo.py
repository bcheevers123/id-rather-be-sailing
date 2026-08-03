from pathlib import Path
import responses

from pipeline.adapters.arlo import ArloAdapter
from pipeline.adapters.base import Offering

FIXTURE_HTML = Path("tests/pipeline/fixtures/arlo_msa_course_page.html").read_text(encoding="utf-8")

MSA_PROVIDER = {
    "id": "maritime-skills-academy-dover",
    "official_name": "Maritime Skills Academy (Dover) part of Viking Maritime Group",
    "website": "https://www.maritimeskillsacademy.com/",
}


@responses.activate
def test_arlo_extracts_offerings():
    responses.add(
        responses.GET,
        "https://www.maritimeskillsacademy.com/courses/stcw-basic-safety-training",
        body=FIXTURE_HTML,
        status=200,
    )
    adapter = ArloAdapter(
        subdomain="maritimeskillsacademy",
        course_path="/courses/stcw-basic-safety-training",
        course_id="pst",
    )
    offerings = adapter.fetch(MSA_PROVIDER)
    assert len(offerings) >= 5


@responses.activate
def test_arlo_offering_has_required_fields():
    responses.add(
        responses.GET,
        "https://www.maritimeskillsacademy.com/courses/stcw-basic-safety-training",
        body=FIXTURE_HTML,
        status=200,
    )
    adapter = ArloAdapter(
        subdomain="maritimeskillsacademy",
        course_path="/courses/stcw-basic-safety-training",
        course_id="pst",
    )
    offerings = adapter.fetch(MSA_PROVIDER)
    assert len(offerings) > 0
    o = offerings[0]
    assert isinstance(o, Offering)
    assert o.start_date is not None
    assert o.currency == "GBP"
    assert o.delivery_format == "in_person"
    assert o.course_id == "pst"
    assert o.provider_id == "maritime-skills-academy-dover"


@responses.activate
def test_arlo_http_error_returns_empty():
    responses.add(
        responses.GET,
        "https://www.maritimeskillsacademy.com/courses/stcw-basic-safety-training",
        status=503,
    )
    adapter = ArloAdapter(
        subdomain="maritimeskillsacademy",
        course_path="/courses/stcw-basic-safety-training",
        course_id="pst",
    )
    offerings = adapter.fetch(MSA_PROVIDER)
    assert offerings == []
