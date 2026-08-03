"""Tests for the Blackpool Fleetwood Nautical Campus adapter."""
from pathlib import Path
from unittest.mock import patch

import responses

from pipeline.adapters.blackpool import (
    BlackpoolAdapter,
    STCW_COURSE_PAGE,
    _extract_course_links,
    _extract_course_name,
    _map_course_name,
    _extract_price,
    _parse_course_page,
)
from bs4 import BeautifulSoup

LISTING_FIXTURE = Path("tests/pipeline/fixtures/blackpool_listing.html").read_text(encoding="utf-8")
COURSE_FIXTURE = Path("tests/pipeline/fixtures/blackpool_course_fpff.html").read_text(encoding="utf-8")

PROVIDER = {
    "id": "blackpool-and-the-fylde-college",
    "official_name": "Blackpool and The Fylde College",
    "website": "https://fleetwoodnautical.blackpool.ac.uk/maritime",
}

COURSE_URL = "https://fleetwoodnautical.blackpool.ac.uk/course/mx1ec459"


# --- Unit tests for helper functions ---

def test_map_course_name_fpff():
    assert _map_course_name("Fire Prevention and Fire Fighting (FPFF)") == "fpff"


def test_map_course_name_pst():
    assert _map_course_name("Personal Survival Techniques") == "pst"


def test_map_course_name_efa():
    assert _map_course_name("Elementary First Aid (EFA)") == "efa"


def test_map_course_name_pssr():
    assert _map_course_name("Personal Safety and Social Responsibilities (PSSR)") == "pssr"


def test_map_course_name_pscrb():
    assert _map_course_name("Proficiency in Survival Craft and Rescue Boats (PSCRB)") == "pscrb"


def test_map_course_name_aff():
    assert _map_course_name("Advanced Fire Fighting (AFF)") == "aff"


def test_map_course_name_frb():
    assert _map_course_name("Fast Rescue Boat (FRB)") == "frb"


def test_map_course_name_unknown_returns_none():
    assert _map_course_name("Something Completely Unknown XYZ") is None


def test_extract_price_simple():
    assert _extract_price("2 Days/ £420") == 420.0


def test_extract_price_with_comma():
    assert _extract_price("1 Week/ £1,340") == 1340.0


def test_extract_price_no_price():
    assert _extract_price("Fleetwood Nautical Campus") is None


def test_extract_course_links_from_listing():
    links = _extract_course_links(LISTING_FIXTURE)
    assert len(links) == 8
    assert all("fleetwoodnautical.blackpool.ac.uk/course/mx1ec" in url for url in links)


def test_extract_course_links_deduplicates():
    html = """<html><body>
    <a href="/course/mx1ec244">Course A</a>
    <a href="/course/mx1ec244">Course A (duplicate)</a>
    <a href="/course/mx1ec459">Course B</a>
    </body></html>"""
    links = _extract_course_links(html)
    assert len(links) == 2


def test_extract_course_name_from_mailto():
    soup = BeautifulSoup(COURSE_FIXTURE, "lxml")
    name = _extract_course_name(soup)
    assert name == "Fire Prevention and Fire Fighting (FPFF)"


def test_extract_course_name_from_title():
    html = "<html><head><title>Elementary First Aid | Fleetwood Nautical Campus</title></head><body></body></html>"
    soup = BeautifulSoup(html, "lxml")
    name = _extract_course_name(soup)
    assert name == "Elementary First Aid"


# --- Parsing tests ---

def test_parse_course_page_extracts_dates():
    offerings = _parse_course_page(COURSE_FIXTURE, COURSE_URL, PROVIDER)
    assert len(offerings) == 2
    dates = {o.start_date for o in offerings}
    assert "2026-09-15" in dates
    assert "2026-11-10" in dates


def test_parse_course_page_extracts_price():
    offerings = _parse_course_page(COURSE_FIXTURE, COURSE_URL, PROVIDER)
    assert all(o.price == 420.0 for o in offerings)
    assert all(o.currency == "GBP" for o in offerings)


def test_parse_course_page_sets_course_id():
    offerings = _parse_course_page(COURSE_FIXTURE, COURSE_URL, PROVIDER)
    assert all(o.course_id == "fpff" for o in offerings)


def test_parse_course_page_booking_url_is_none():
    offerings = _parse_course_page(COURSE_FIXTURE, COURSE_URL, PROVIDER)
    assert all(o.booking_url is None for o in offerings)


def test_parse_course_page_provider_id():
    offerings = _parse_course_page(COURSE_FIXTURE, COURSE_URL, PROVIDER)
    assert all(o.provider_id == "blackpool-and-the-fylde-college" for o in offerings)


def test_parse_course_page_offering_id_format():
    offerings = _parse_course_page(COURSE_FIXTURE, COURSE_URL, PROVIDER)
    assert all(o.id.startswith("fpff-blackpool-") for o in offerings)


def test_parse_course_page_unknown_course_returns_empty():
    html = """<html><head><title>Unknown Course XYZ | Fleetwood Nautical Campus</title></head>
    <body><div id="occ"><table><tbody>
    <tr><td data-swiftype-index="true">10 Jan 2027</td><td>Fleetwood</td><td>1 Day/ £200</td>
    <td><a href="mailto:maritime@blackpool.ac.uk?subject=Course Enquiry: Unknown Course XYZ">Enquire</a></td></tr>
    </tbody></table></div></body></html>"""
    offerings = _parse_course_page(html, COURSE_URL, PROVIDER)
    assert offerings == []


# --- Integration tests (mocked HTTP) ---

@responses.activate
def test_blackpool_adapter_fetch_returns_list():
    responses.add(responses.GET, STCW_COURSE_PAGE, body=LISTING_FIXTURE, status=200)
    # Mock each of the 8 course pages with the FPFF fixture
    for path in [
        "mx1ec244", "mx1ec459", "mx1ec301", "mx1ec388",
        "mx1ec502", "mx1ec611", "mx1ec720", "mx1ec830",
    ]:
        responses.add(
            responses.GET,
            f"https://fleetwoodnautical.blackpool.ac.uk/course/{path}",
            body=COURSE_FIXTURE,
            status=200,
        )
    with patch("time.sleep"):
        adapter = BlackpoolAdapter()
        result = adapter.fetch(PROVIDER)
    assert isinstance(result, list)
    # 8 course pages × 2 date rows each — but only those that map succeed
    # FPFF fixture maps to fpff for all 8 pages
    assert len(result) > 0


@responses.activate
def test_blackpool_adapter_listing_failure_returns_empty():
    responses.add(responses.GET, STCW_COURSE_PAGE, status=503)
    with patch("time.sleep"):
        adapter = BlackpoolAdapter()
        result = adapter.fetch(PROVIDER)
    assert result == []


@responses.activate
def test_blackpool_adapter_course_page_failure_skips():
    responses.add(responses.GET, STCW_COURSE_PAGE, body=LISTING_FIXTURE, status=200)
    for path in [
        "mx1ec244", "mx1ec459", "mx1ec301", "mx1ec388",
        "mx1ec502", "mx1ec611", "mx1ec720", "mx1ec830",
    ]:
        responses.add(
            responses.GET,
            f"https://fleetwoodnautical.blackpool.ac.uk/course/{path}",
            status=404,
        )
    with patch("time.sleep"):
        adapter = BlackpoolAdapter()
        result = adapter.fetch(PROVIDER)
    # All course pages failed — should return empty list, not raise
    assert result == []
