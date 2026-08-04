"""Scottish Maritime Academy at NE Scotland College (smaritime.co.uk) adapter.

smaritime.co.uk 302-redirects to nescol.ac.uk. Course pages live at
https://www.nescol.ac.uk/courses/<slug>/

Each course page shows date/duration/fee information in two complementary
structures:
  1. Definition list  <dt>Starts</dt><dd>25 Nov 2026</dd>
  2. Booking blocks   <h4>Starts25 Nov 2026</h4> … <a …>Book Online</a>
     (one block per date when multiple start dates exist)

The booking blocks are the canonical source because they contain one entry per
date AND carry the individual booking link.  We parse those blocks and fall back
to the <dt>/<dd> form for single-date courses that lack a booking block.

Date format on the site: "25 Nov 2026"  →  ISO-8601 "2026-11-25"
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

BASE_URL = "https://www.nescol.ac.uk"

# All known STCW-relevant course slugs at the Scottish Maritime Academy.
# Keyed by our internal course_id.
_COURSE_SLUGS: dict[str, str] = {
    "pssr": "stcw-personal-safety-and-social-responsibilities",
    "efa":  "stcw-elementary-first-aid-and-seafish-first-aid",
    "pst":  "stcw-personal-survival-techniques-seafish-sea-survival",
    "fpff": "seafish-fire-fighting-including-refresher-training",
}

# Site date format: "25 Nov 2026"
_DATE_FMT = "%d %b %Y"

# Matches "25 Nov 2026" anywhere in a string
_DATE_RE = re.compile(
    r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})\b",
    re.I,
)

# The booking block heading text looks like "Starts25 Nov 2026" (no space) or
# "Starts 25 Nov 2026" depending on whitespace collapsing.
_STARTS_RE = re.compile(r"^Starts\s*(.+)$", re.I)


def _parse_date(text: str) -> str | None:
    """Parse '25 Nov 2026' → '2026-11-25', or return None on failure."""
    text = text.strip()
    try:
        return datetime.strptime(text, _DATE_FMT).date().isoformat()
    except ValueError:
        return None


def _extract_booking_blocks(soup: BeautifulSoup) -> list[dict]:
    """Return list of {start_date, duration, price, booking_url} from booking blocks.

    Each booking date lives in a <div class="application-item"> containing:
      <ul>
        <li class="app-block"><h4><span class="highlight">Starts</span>
                                   <span class="value">25 Nov 2026</span></h4></li>
        <li class="app-block"><h4><span class="highlight">Duration</span>
                                   <span class="value">1 day</span></h4></li>
        <li class="app-block"><h4><span class="highlight">Fees</span>
                                   <span class="value">£195.00</span></h4></li>
      </ul>
      <div class="application-cta …">
        <a href="…booking-url…">Book Online</a>
      </div>
    """
    blocks: list[dict] = []

    for card in soup.find_all("div", class_="application-item"):
        start_iso: str | None = None
        duration: str | None = None
        price: float | None = None
        booking_url: str | None = None

        for li in card.find_all("li", class_="app-block"):
            h4 = li.find("h4")
            if not h4:
                continue
            highlight = h4.find("span", class_="highlight")
            value_span = h4.find("span", class_="value")
            if not highlight or not value_span:
                continue
            label = highlight.get_text(strip=True).lower()
            value = value_span.get_text(" ", strip=True)

            if label == "starts":
                dm = _DATE_RE.search(value)
                if dm:
                    start_iso = _parse_date(dm.group(1))
            elif label == "duration":
                duration = value
            elif label in ("fees", "fee"):
                fee_text = re.sub(r"[^\d.]", "", value)
                try:
                    price = float(fee_text) if fee_text else None
                except ValueError:
                    price = None

        # Booking link
        cta = card.find("div", class_="application-cta")
        if cta:
            a = cta.find("a", href=True)
            if a:
                href = a["href"]
                booking_url = href if href.startswith("http") else BASE_URL + href

        if start_iso:
            blocks.append(
                {
                    "start_date": start_iso,
                    "duration": duration,
                    "price": price,
                    "booking_url": safe_url(booking_url),
                }
            )

    return blocks


def _extract_dt_dd_dates(soup: BeautifulSoup) -> list[dict]:
    """Fallback: pull start date(s) from <dt>Starts</dt><dd>…</dd> pairs."""
    results: list[dict] = []
    for dt in soup.find_all("dt"):
        if dt.get_text(strip=True).lower() != "starts":
            continue
        dd = dt.find_next_sibling("dd")
        if not dd:
            continue
        for dm in _DATE_RE.finditer(dd.get_text(" ", strip=True)):
            iso = _parse_date(dm.group(1))
            if iso:
                results.append({"start_date": iso, "duration": None, "price": None, "booking_url": None})

    # Also look for fee
    for dt in soup.find_all("dt"):
        if dt.get_text(strip=True).lower() not in ("fees", "fee"):
            continue
        dd = dt.find_next_sibling("dd")
        if dd:
            fee_text = re.sub(r"[^\d.]", "", dd.get_text(strip=True))
            try:
                price = float(fee_text) if fee_text else None
            except ValueError:
                price = None
            for r in results:
                if r["price"] is None:
                    r["price"] = price

    return results


def _duration_days(text: str | None) -> float | None:
    """Convert '1 day', '1/2 day', '2 weeks' → float days."""
    if not text:
        return None
    t = text.lower().strip()
    if "week" in t:
        m = re.search(r"(\d+(?:\.\d+)?)", t)
        return float(m.group(1)) * 7 if m else None
    if "1/2" in t or "half" in t:
        return 0.5
    m = re.search(r"(\d+(?:\.\d+)?)", t)
    return float(m.group(1)) if m else None


class SmaritimeAdapter(BaseAdapter):
    """Scrapes STCW course dates from Scottish Maritime Academy (nescol.ac.uk)."""

    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        all_offerings: list[Offering] = []
        now = datetime.now(timezone.utc).isoformat()

        for course_id, slug in _COURSE_SLUGS.items():
            url = f"{BASE_URL}/courses/{slug}/"
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("smaritime: fetch failed %s: %s", url, exc)
                time.sleep(2)
                continue
            time.sleep(2)

            try:
                offerings = self._parse_course_page(
                    resp.text, url, course_id, provider, now
                )
                all_offerings.extend(offerings)
            except Exception as exc:
                logger.warning("smaritime: parse failed %s: %s", url, exc)

        logger.info("smaritime adapter: %d offerings total", len(all_offerings))
        return all_offerings

    def _parse_course_page(
        self,
        html: str,
        page_url: str,
        course_id: str,
        provider: dict,
        now: str,
    ) -> list[Offering]:
        soup = BeautifulSoup(html, "lxml")

        # Primary: booking blocks (handles multi-date pages)
        blocks = _extract_booking_blocks(soup)

        # Fallback: dt/dd pairs
        if not blocks:
            blocks = _extract_dt_dd_dates(soup)

        if not blocks:
            logger.debug("smaritime: no dates found for %s", page_url)
            return []

        offerings: list[Offering] = []
        seen: set[str] = set()

        for block in blocks:
            start_iso = block["start_date"]
            if start_iso in seen:
                continue
            seen.add(start_iso)

            dur = _duration_days(block.get("duration"))
            price = block.get("price")
            booking_url = block.get("booking_url")

            # Derive end_date from duration_days where available
            if dur is not None and dur >= 1:
                from datetime import timedelta
                end_iso = (
                    datetime.fromisoformat(start_iso) + timedelta(days=int(dur) - 1)
                ).date().isoformat()
            else:
                end_iso = start_iso

            offerings.append(
                Offering(
                    id=f"{course_id}-smaritime-{start_iso}",
                    course_id=course_id,
                    provider_id=provider["id"],
                    start_date=start_iso,
                    end_date=end_iso,
                    timezone="Europe/London",
                    duration_days=dur,
                    price=price,
                    currency="GBP" if price is not None else None,
                    vat_included=None,
                    delivery_format="in_person",
                    availability=None,
                    booking_url=booking_url,
                    source_url=page_url,
                    last_verified=now,
                    freshness_status="verified",
                )
            )

        logger.info(
            "smaritime: %d offerings for course_id=%s (%s)",
            len(offerings),
            course_id,
            page_url,
        )
        return offerings
