# Task 7 Brief: BaseAdapter, Offering dataclass, Arlo adapter

## Context

Task 7 of the "I'd Rather Be Sailing" plan. Tasks 1–6 are complete on branch `feature/maritime-training`. You are implementing:
- `pipeline/adapters/base.py` — `Offering` dataclass + `BaseAdapter` ABC
- `pipeline/adapters/arlo.py` — adapter for Arlo-hosted course pages (used by Maritime Skills Academy and others)
- An HTML fixture from the live MSA site
- Tests using the `responses` library (already in requirements)

## Working directory

`C:\Users\BarryCheevers\OneDrive - Anomali\Desktop\Fun\I'd Rather Be Sailing`
Branch: `feature/maritime-training`

Python venv: `.venv`. `pip install -r requirements.txt`. Both `responses` and `python-dateutil` are already in requirements.txt.

## Files to create

- `pipeline/adapters/base.py`
- `pipeline/adapters/arlo.py`
- `tests/pipeline/fixtures/arlo_msa_course_page.html`
- `tests/pipeline/test_adapters_arlo.py`

## Step 1 — Fetch the Arlo fixture

```python
import requests
r = requests.get(
    "https://www.maritimeskillsacademy.com/courses/stcw-basic-safety-training",
    headers={"User-Agent": "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; +https://github.com/bcheevers123/id-rather-be-sailing)"},
    timeout=30,
)
open("tests/pipeline/fixtures/arlo_msa_course_page.html", "w", encoding="utf-8").write(r.text)
print(len(r.text), "bytes saved")
```

Then inspect the fixture HTML to understand how dates are structured before writing the parser.

## Step 2 — Write tests/pipeline/test_adapters_arlo.py

```python
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
```

## Step 3 — Run failing tests (red phase)

```bash
pytest tests/pipeline/test_adapters_arlo.py -v
```
Expected: ImportError.

## Step 4 — Create pipeline/adapters/base.py

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Offering:
    id: str
    course_id: str
    provider_id: str
    start_date: str
    end_date: str
    timezone: str
    duration_days: float | None
    price: float | None
    currency: str | None
    vat_included: bool | None
    delivery_format: str
    availability: str | None
    booking_url: str | None
    source_url: str
    last_verified: str
    freshness_status: str = "verified"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "course_id": self.course_id,
            "provider_id": self.provider_id,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "timezone": self.timezone,
            "duration_days": self.duration_days,
            "price": self.price,
            "currency": self.currency,
            "vat_included": self.vat_included,
            "delivery_format": self.delivery_format,
            "availability": self.availability,
            "booking_url": self.booking_url,
            "source_url": self.source_url,
            "last_verified": self.last_verified,
            "freshness_status": self.freshness_status,
        }


class BaseAdapter(ABC):
    @abstractmethod
    def fetch(self, provider: dict) -> list[Offering]:
        """Fetch offerings for the given provider. Returns empty list on any failure."""
```

## Step 5 — Create pipeline/adapters/arlo.py

**IMPORTANT:** Before writing the parser, inspect the actual fixture HTML to understand the page structure. The plan's suggested CSS selectors may not match the real page. Look for elements that contain date strings (e.g., "12 Aug 2026" or "12-14 Aug 2026"), prices (e.g., "£950"), and registration links. Adapt the selectors accordingly.

The Arlo MSA page typically shows upcoming sessions in a list/table. Common patterns:
- Sessions in `<ul>` items with date + price + registration button
- Date format: "12 Aug 2026" or "12-14 Aug 2026"
- Price: "£950" or "£950 + VAT"

Base implementation to adapt from:

```python
import hashlib
import logging
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

from pipeline.adapters.base import BaseAdapter, Offering

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; +https://github.com/bcheevers123/id-rather-be-sailing)"

_PRICE_RE = re.compile(r"£\s*([\d,]+(?:\.\d{2})?)", re.I)
_DATE_RANGE_RE = re.compile(
    r"(\d{1,2})\s*[–\-]\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})",
)
_SINGLE_DATE_RE = re.compile(
    r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})",
)


class ArloAdapter(BaseAdapter):
    def __init__(self, subdomain: str, course_path: str, course_id: str):
        self.subdomain = subdomain
        self.course_path = course_path
        self.course_id = course_id
        base_domain = f"www.{subdomain}.com"
        self.source_url = f"https://{base_domain}{course_path}"

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        try:
            resp = session.get(self.source_url, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("Arlo fetch failed for %s: %s", self.source_url, e)
            return []

        time.sleep(2)
        return self._parse(resp.text, provider)

    def _parse(self, html: str, provider: dict) -> list[Offering]:
        soup = BeautifulSoup(html, "lxml")
        offerings: list[Offering] = []
        now = datetime.now(timezone.utc).isoformat()

        # Adapt these selectors based on actual fixture structure
        date_containers = (
            soup.find_all("li", class_=re.compile(r"session|event|date", re.I))
            or soup.find_all("tr", class_=re.compile(r"session|event|row", re.I))
            or soup.find_all("div", class_=re.compile(r"session|event|upcoming", re.I))
        )

        for container in date_containers:
            text = container.get_text(" ", strip=True)
            start_date, end_date = _extract_date_range(text)
            if not start_date:
                continue

            price, vat_included = _extract_price(text)
            booking_link = _extract_booking_link(container)

            offering_id = _make_offering_id(self.course_id, provider["id"], start_date)
            offerings.append(Offering(
                id=offering_id,
                course_id=self.course_id,
                provider_id=provider["id"],
                start_date=start_date,
                end_date=end_date or start_date,
                timezone="Europe/London",
                duration_days=None,
                price=price,
                currency="GBP" if price is not None else None,
                vat_included=vat_included,
                delivery_format="in_person",
                availability=None,
                booking_url=booking_link,
                source_url=self.source_url,
                last_verified=now,
                freshness_status="verified",
            ))

        logger.info("Arlo adapter extracted %d offerings from %s", len(offerings), self.source_url)
        return offerings


def _subdomain_to_domain(subdomain: str) -> str:
    return f"www.{subdomain}.com"


def _extract_date_range(text: str) -> tuple[str | None, str | None]:
    m = _DATE_RANGE_RE.search(text)
    if m:
        day1, day2, month, year = m.groups()
        try:
            start = dateutil_parser.parse(f"{day1} {month} {year}").date().isoformat()
            end = dateutil_parser.parse(f"{day2} {month} {year}").date().isoformat()
            return start, end
        except Exception:
            pass
    m2 = _SINGLE_DATE_RE.search(text)
    if m2:
        day, month, year = m2.groups()
        try:
            start = dateutil_parser.parse(f"{day} {month} {year}").date().isoformat()
            return start, start
        except Exception:
            pass
    return None, None


def _extract_price(text: str) -> tuple[float | None, bool | None]:
    m = _PRICE_RE.search(text)
    if not m:
        return None, None
    price = float(m.group(1).replace(",", ""))
    vat_mentioned = "vat" in text.lower()
    vat_included = ("incl" in text.lower() and vat_mentioned) or None if not vat_mentioned else None
    return price, vat_included


def _extract_booking_link(container) -> str | None:
    link = container.find("a", href=re.compile(r"arlo\.co|register|book", re.I))
    if link:
        return link.get("href")
    return None


def _make_offering_id(course_id: str, provider_id: str, start_date: str) -> str:
    raw = f"{course_id}-{provider_id}-{start_date}"
    return raw[:80]
```

## Step 6 — Debugging guidance if tests fail

If `test_arlo_extracts_offerings` fails with `len(offerings) == 0`:

1. Inspect the fixture: look at the HTML structure around dates
2. Try broader selectors — scan ALL text in the page for date patterns using `soup.get_text()`
3. Or find container elements using: `soup.find_all(string=_DATE_RANGE_RE)` or `soup.find_all(string=_SINGLE_DATE_RE)` then navigate up to their parent containers
4. The key constraint is: dates must come from the real HTML, never invented

If the page has no upcoming dates (possible if the fixture was fetched during a gap), try a broader approach — scrape ALL text blocks and filter by date pattern.

## Step 7 — Run all tests

```bash
pytest tests/pipeline/test_adapters_arlo.py -v
pytest -v
```
All 30 prior tests must still pass.

## Step 8 — Commit

```bash
git add pipeline/adapters/ tests/pipeline/test_adapters_arlo.py tests/pipeline/fixtures/arlo_msa_course_page.html
git commit -m "feat: BaseAdapter, Offering dataclass, Arlo adapter"
```

## Global constraints

- User-Agent exactly: `Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; +https://github.com/bcheevers123/id-rather-be-sailing)`
- `fetch()` must always return `[]` on any HTTP or parse error — never raise
- `Offering` fields must match `offering.schema.json` exactly (all 16 fields)
- `freshness_status` must be one of: `verified`, `recently_checked`, `stale`, `source_unavailable`, `no_public_schedule`
- `delivery_format` must be one of: `in_person`, `blended`, `online`, `unknown`
- No fabricated dates or prices — only from real fixture HTML
- Tests use `@responses.activate` mock, NOT live HTTP

## Report file

Write your report to: `.superpowers/sdd/2026-08-03-maritime-training-plan/task-7-report.md`

Return: Status, commit hash, test summary, concerns (especially about fixture structure).
