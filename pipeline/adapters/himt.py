"""Hindustan Institute of Maritime Training (HIMT) adapter.

himtoffshore.com redirects (HTTP 301) to himtmarine.com/uk-mca-approved-course/.
The site is WordPress with static HTML — no JavaScript execution required.

Course pages scraped:
  - BST (combined PST+FPFF+EFA+PSSR):
      /basic-modular-courses/basic-stcw-safety-training-coursebst/
  - PSSR standalone:
      /basic-modular-courses/personal-safety-social-responsibilities/
  - EFA:
      /basic-modular-courses/elementary-first-aid-efa/
  - AFF:
      /advanced-modular-courses/advanced-fire-fightingaff/
  - PSCRB:
      /advanced-modular-courses/proficiency-in-survival-craft-rescue-boats/
  - MFA:
      /advanced-modular-courses/medical-first-aid/
  - MC:
      /advanced-modular-courses/masters-medical-care-course/

Date format on batch tables: "DD Mon YYYY" (e.g. "10 Aug 2026").
Each row typically spans "DD Mon YYYY - DD Mon YYYY".
"""

import logging
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from pipeline.adapters.base import BaseAdapter, Offering
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; "
    "+https://github.com/bcheevers123/id-rather-be-sailing)"
)

BASE_URL = "https://himtmarine.com"

# (course_id, url_path, duration_days)
_COURSE_PAGES: list[tuple[str, str, int]] = [
    # BST combines PST+FPFF+EFA+PSSR — emit one entry per module
    ("pst",   "/basic-modular-courses/basic-stcw-safety-training-coursebst/",       11),
    ("fpff",  "/basic-modular-courses/basic-stcw-safety-training-coursebst/",       11),
    ("efa",   "/basic-modular-courses/basic-stcw-safety-training-coursebst/",       11),
    ("pssr",  "/basic-modular-courses/personal-safety-social-responsibilities/",      4),
    # EFA standalone page (may have "no batch dates" — handled gracefully)
    # ("efa", "/basic-modular-courses/elementary-first-aid-efa/", 3),
    ("aff",   "/advanced-modular-courses/advanced-fire-fightingaff/",                5),
    ("pscrb", "/advanced-modular-courses/proficiency-in-survival-craft-rescue-boats/", 5),
    ("mfa",   "/advanced-modular-courses/medical-first-aid/",                        4),
    ("mc",    "/advanced-modular-courses/masters-medical-care-course/",             10),
]

# "10 Aug 2026" or "10 Aug 2026 - 21 Aug 2026"
_DATE_RE = re.compile(
    r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})",
    re.I,
)

# Price patterns: "9,900Rs" / "₹ 9,900" / "9900Rs" etc.
_PRICE_RE = re.compile(r"(?:₹\s*|Rs\.?\s*)([\d,]+)", re.I)


def _parse_date(day: str, mon: str, year: str) -> str:
    """Return ISO date string from components."""
    return datetime.strptime(f"{int(day):02d} {mon.capitalize()} {year}", "%d %b %Y").date().isoformat()


def _extract_batches(html: str) -> list[tuple[str, str, float | None]]:
    """Return list of (start_iso, end_iso, price_inr | None) tuples from page HTML."""
    soup = BeautifulSoup(html, "lxml")
    batches: list[tuple[str, str, float | None]] = []
    seen: set[str] = set()

    # Strategy 1: look for table rows that contain dates
    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"])
        row_text = " ".join(c.get_text(" ", strip=True) for c in cells)

        dates = _DATE_RE.findall(row_text)
        if not dates:
            continue

        start_iso = _parse_date(*dates[0])
        end_iso = _parse_date(*dates[-1]) if len(dates) > 1 else start_iso

        if start_iso in seen:
            continue
        seen.add(start_iso)

        # Try to extract price from the row
        price: float | None = None
        pm = _PRICE_RE.search(row_text)
        if pm:
            try:
                price = float(pm.group(1).replace(",", ""))
            except ValueError:
                pass

        batches.append((start_iso, end_iso, price))

    if batches:
        return batches

    # Strategy 2: scan all text nodes for date ranges (card-based layout)
    for el in soup.find_all(string=_DATE_RE):
        text = str(el).strip()
        dates = _DATE_RE.findall(text)
        if not dates:
            continue

        start_iso = _parse_date(*dates[0])
        end_iso = _parse_date(*dates[-1]) if len(dates) > 1 else start_iso

        if start_iso in seen:
            continue
        seen.add(start_iso)

        # Look for price in parent elements
        price = None
        parent = el.parent
        for _ in range(5):
            if parent is None:
                break
            parent_text = parent.get_text(" ", strip=True)
            pm = _PRICE_RE.search(parent_text)
            if pm:
                try:
                    price = float(pm.group(1).replace(",", ""))
                except ValueError:
                    pass
                break
            parent = parent.parent

        batches.append((start_iso, end_iso, price))

    return batches


class HimtAdapter(BaseAdapter):
    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        now = datetime.now(timezone.utc).isoformat()
        all_offerings: list[Offering] = []

        # Track already-emitted (course_id, start_date) pairs to avoid duplicates
        # when the same URL is scraped for multiple course IDs (BST page)
        seen_bst_dates: set[str] = set()

        for course_id, path, duration_days in _COURSE_PAGES:
            url = BASE_URL + path
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as e:
                logger.warning("HIMT fetch failed %s: %s", url, e)
                time.sleep(2)
                continue
            time.sleep(2)

            try:
                batches = _extract_batches(resp.text)
            except Exception as e:
                logger.warning("HIMT parse failed %s: %s", url, e)
                continue

            if not batches:
                logger.debug("HIMT: no batches found for course_id=%s (%s)", course_id, url)
                continue

            for start_iso, end_iso, price in batches:
                # Deduplicate BST-sourced entries across PST/FPFF/EFA
                dedup_key = f"{course_id}-{start_iso}"
                if path.endswith("bststsdsd/") or "basic-stcw-safety-training-coursebst" in path:
                    if dedup_key in seen_bst_dates:
                        continue
                    seen_bst_dates.add(dedup_key)

                offering = Offering(
                    id=f"{course_id}-himt-{start_iso}",
                    course_id=course_id,
                    provider_id=provider["id"],
                    start_date=start_iso,
                    end_date=end_iso,
                    timezone="Asia/Kolkata",
                    duration_days=float(duration_days),
                    price=price,
                    currency="INR" if price is not None else None,
                    vat_included=None,
                    delivery_format="in_person",
                    availability=None,
                    booking_url=safe_url("https://himt.co.in"),
                    source_url=url,
                    last_verified=now,
                    freshness_status="verified",
                )
                all_offerings.append(offering)

        logger.info("HIMT adapter: %d offerings total", len(all_offerings))
        return all_offerings
