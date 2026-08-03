"""Seafood Cornwall Training Ltd adapter.

Scrapes the course-dates listing page at seafoodcornwalltraining.co.uk/course-dates/
to find upcoming STCW-related courses (PST, EFA, FPFF, PSSR, BST/Basic Safety).
For each matching course entry it follows the link to the individual course page
to extract a price, then yields an Offering.
"""
import logging
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

from pipeline.adapters.base import BaseAdapter, Offering
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; "
    "+https://github.com/bcheevers123/id-rather-be-sailing)"
)

BASE_URL = "https://www.seafoodcornwalltraining.co.uk"
LISTING_URL = BASE_URL + "/course-dates/"

# Keywords used to detect STCW-related courses in the listing text
STCW_KEYWORDS = re.compile(
    r"\b(PST|EFA|FPFF|PSSR|STCW|Basic\s+Safety|Personal\s+Survival|"
    r"Elementary\s+First\s+Aid|Fire\s+Prevention|Personal\s+Safety"
    r"|Basic\s+Safety\s+Training|BST)\b",
    re.I,
)

# Map text patterns to course_id
_COURSE_ID_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bPersonal\s+Survival\b|\bPST\b", re.I), "pst"),
    (re.compile(r"\bElementary\s+First\s+Aid\b|\bEFA\b", re.I), "efa"),
    (re.compile(r"\bFire\s+Prevention\b|\bFPFF\b", re.I), "fpff"),
    (re.compile(r"\bPersonal\s+Safety\b|\bPSSR\b", re.I), "pssr"),
    (re.compile(r"\bBasic\s+Safety\s+Training\b|\bBST\b", re.I), "pst"),
]

# Date: "10 August 2026" / "10 Aug 2026"
_DATE_RE = re.compile(r"\b(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\b")

# Price: "£550" or "£550.00"
_PRICE_RE = re.compile(r"[£\xA3]\s*([\d,]+(?:\.\d{2})?)")


def _map_course_id(text: str) -> str | None:
    for pattern, course_id in _COURSE_ID_MAP:
        if pattern.search(text):
            return course_id
    return None


def _extract_price(html: str) -> tuple[float | None, bool | None]:
    """Return (price_float, vat_included) from page HTML."""
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)
    m = _PRICE_RE.search(text)
    if not m:
        return None, None
    try:
        price = float(m.group(1).replace(",", ""))
    except ValueError:
        return None, None
    text_lower = text.lower()
    if "incl" in text_lower and "vat" in text_lower:
        vat_included = True
    elif "excl" in text_lower and "vat" in text_lower:
        vat_included = False
    else:
        vat_included = None
    return price, vat_included


class SeafoodCornwallAdapter(BaseAdapter):
    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        # --- Step 1: fetch the listing page ---
        try:
            resp = session.get(LISTING_URL, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("SeafoodCornwall: failed to fetch listing %s: %s", LISTING_URL, e)
            return []
        time.sleep(2)

        # --- Step 2: parse listing for STCW entries ---
        try:
            entries = self._parse_listing(resp.text)
        except Exception as e:
            logger.warning("SeafoodCornwall: failed to parse listing: %s", e)
            return []

        if not entries:
            logger.info("SeafoodCornwall: no STCW entries found on listing page")
            return []

        # --- Step 3: for each entry fetch the course page for price ---
        now = datetime.now(timezone.utc).isoformat()
        offerings: list[Offering] = []
        seen: set[str] = set()

        for (course_text, start_date, end_date, course_url) in entries:
            course_id = _map_course_id(course_text)
            if not course_id:
                continue

            offering_id = f"{course_id}-seafood-cornwall-{start_date}"
            if offering_id in seen:
                continue
            seen.add(offering_id)

            price: float | None = None
            vat_included: bool | None = None

            if course_url:
                try:
                    pr = session.get(course_url, timeout=20)
                    pr.raise_for_status()
                    time.sleep(2)
                    price, vat_included = _extract_price(pr.text)
                except Exception as e:
                    logger.warning(
                        "SeafoodCornwall: failed to fetch course page %s: %s", course_url, e
                    )

            offerings.append(
                Offering(
                    id=offering_id,
                    course_id=course_id,
                    provider_id=provider["id"],
                    start_date=start_date,
                    end_date=end_date,
                    timezone="Europe/London",
                    duration_days=None,
                    price=price,
                    currency="GBP" if price is not None else None,
                    vat_included=vat_included,
                    delivery_format="in_person",
                    availability=None,
                    booking_url=safe_url(course_url or LISTING_URL),
                    source_url=LISTING_URL,
                    last_verified=now,
                    freshness_status="verified",
                )
            )

        logger.info("SeafoodCornwall: extracted %d offerings", len(offerings))
        return offerings

    # ------------------------------------------------------------------
    def _parse_listing(
        self, html: str
    ) -> list[tuple[str, str, str, str | None]]:
        """Parse the course-dates listing page.

        Returns a list of (course_text, start_date_iso, end_date_iso, course_url | None)
        for every STCW-related entry found.
        """
        soup = BeautifulSoup(html, "lxml")
        results: list[tuple[str, str, str, str | None]] = []

        # Strategy A: look for table rows
        for row in soup.find_all("tr"):
            text = row.get_text(" ", strip=True)
            if not STCW_KEYWORDS.search(text):
                continue
            dates = _DATE_RE.findall(text)
            if not dates:
                continue
            try:
                start_d = dateutil_parser.parse(dates[0], fuzzy=False).date().isoformat()
                end_d = (
                    dateutil_parser.parse(dates[-1], fuzzy=False).date().isoformat()
                    if len(dates) > 1
                    else start_d
                )
            except Exception:
                continue
            link_tag = row.find("a", href=True)
            course_url = (
                urljoin(BASE_URL, link_tag["href"]) if link_tag else None
            )
            results.append((text, start_d, end_d, course_url))

        # Strategy B: look for list items / divs with STCW keywords and dates
        if not results:
            for el in soup.find_all(
                ["li", "div", "article", "section", "p"],
                string=None,
            ):
                # Avoid deep nesting — only consider leaf-ish elements
                if el.find(["li", "div", "article"]):
                    continue
                text = el.get_text(" ", strip=True)
                if not STCW_KEYWORDS.search(text):
                    continue
                dates = _DATE_RE.findall(text)
                if not dates:
                    continue
                try:
                    start_d = dateutil_parser.parse(dates[0], fuzzy=False).date().isoformat()
                    end_d = (
                        dateutil_parser.parse(dates[-1], fuzzy=False).date().isoformat()
                        if len(dates) > 1
                        else start_d
                    )
                except Exception:
                    continue
                link_tag = el.find("a", href=True)
                if not link_tag:
                    # look at parent
                    parent = el.parent
                    if parent:
                        link_tag = parent.find("a", href=True)
                course_url = (
                    urljoin(BASE_URL, link_tag["href"]) if link_tag else None
                )
                results.append((text, start_d, end_d, course_url))

        # Strategy C: scan full page text for STCW sections via headings/links
        if not results:
            for a in soup.find_all("a", href=True):
                text = a.get_text(" ", strip=True)
                if not STCW_KEYWORDS.search(text):
                    continue
                # Try to find a date near the link
                container = a.parent or a
                container_text = container.get_text(" ", strip=True)
                dates = _DATE_RE.findall(container_text)
                if not dates:
                    continue
                try:
                    start_d = dateutil_parser.parse(dates[0], fuzzy=False).date().isoformat()
                    end_d = (
                        dateutil_parser.parse(dates[-1], fuzzy=False).date().isoformat()
                        if len(dates) > 1
                        else start_d
                    )
                except Exception:
                    continue
                course_url = urljoin(BASE_URL, a["href"])
                results.append((text, start_d, end_d, course_url))

        return results
