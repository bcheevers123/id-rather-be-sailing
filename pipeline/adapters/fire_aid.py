"""Fire Aid Academy Hythe adapter.

Scrapes the Fire Aid booking system (booking.fireaid.com) to discover all
courses on the root listing page, then fetches each individual CourseDates
page for available session dates, prices, and availability labels.

Booking system structure (static HTML, no JS required):
  Root:  https://booking.fireaid.com/
         Lists all courses as <a href="/Home/CourseDates/{guid}">Course Name</a>

  Per-course: https://booking.fireaid.com/Home/CourseDates/{guid}
         Contains an <h2>Available Dates</h2> section with one <li> per session.
         Each <li> holds:
           - a <span> with the availability label (Good Availability / Low Availability / Not Available)
           - a <span data-toggle="tooltip"> with the text:
               "Fire Aid Hythe Academy from DD/MM/YYYY to DD/MM/YYYY - Price (inc. VAT) £NNN.NN"
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

BOOKING_ROOT = "https://booking.fireaid.com"
LISTING_URL = BOOKING_ROOT + "/"

# Maps keywords in course titles to normalised course IDs.
# Checked in order — first match wins.
_COURSE_ID_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"elementary.first.aid|[^a-z]efa[^a-z]", re.I), "efa"),
    (re.compile(r"medical.first.aid|[^a-z]mfa[^a-z]", re.I), "mfa"),
    (re.compile(r"personal.survival.techniques|[^a-z]pst[^a-z]", re.I), "pst"),
    (re.compile(r"fire.prevention.and.fire.fighting|fire.prevention.*fighting|[^a-z]fpff[^a-z]", re.I), "fpff"),
    (re.compile(r"personal.safety.and.social|[^a-z]pssr[^a-z]", re.I), "pssr"),
    (re.compile(r"proficiency.in.survival.craft|[^a-z]pscrb[^a-z]", re.I), "pscrb"),
    (re.compile(r"advanced.fire.fighting|[^a-z]aff[^a-z]", re.I), "aff"),
    (re.compile(r"marine.fire.arms|[^a-z]mfa[^a-z]", re.I), "mfa"),
    (re.compile(r"fast.rescue.boat|[^a-z]frb[^a-z]", re.I), "frb"),
    (re.compile(r"medical.care|[^a-z]mc[^a-z]", re.I), "mc"),
]

# DD/MM/YYYY date pattern
_DATE_RE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")

# Price: £NNN.NN  (HTML entity or literal pound sign)
_PRICE_RE = re.compile(r"[££](\d+(?:\.\d+)?)")

# Availability label normalisation
_AVAIL_MAP = {
    "good availability": "available",
    "low availability": "limited",
    "not available": "full",
}


def _course_id_from_text(text: str) -> str | None:
    """Return a normalised course ID by matching text against the keyword map."""
    padded = f" {text} "
    for pattern, course_id in _COURSE_ID_MAP:
        if pattern.search(padded):
            return course_id
    return None


class FireAidAdapter(BaseAdapter):
    """Adapter for Fire Aid Academy Hythe (fire-aid-academy-hythe)."""

    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        # Step 1 — fetch the root listing page
        try:
            resp = session.get(LISTING_URL, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("FireAid listing fetch failed: %s", exc)
            return []
        time.sleep(2)

        # Step 2 — extract per-course CourseDates URLs
        try:
            course_links = self._extract_course_links(resp.text)
        except Exception as exc:
            logger.warning("FireAid listing parse failed: %s", exc)
            return []

        if not course_links:
            logger.warning("FireAid: no course links found on listing page")
            return []

        # Step 3 — fetch each course dates page
        all_offerings: list[Offering] = []
        for course_name, course_url in course_links:
            try:
                resp = session.get(course_url, timeout=20)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("FireAid course fetch failed %s: %s", course_url, exc)
                time.sleep(2)
                continue
            time.sleep(2)
            try:
                offerings = self._parse_course_page(
                    resp.text, course_url, course_name, provider
                )
                all_offerings.extend(offerings)
            except Exception as exc:
                logger.warning("FireAid course parse failed %s: %s", course_url, exc)

        logger.info("FireAid adapter: %d offerings total", len(all_offerings))
        return all_offerings

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_course_links(self, html: str) -> list[tuple[str, str]]:
        """Return list of (course_name, absolute_url) for each course listed."""
        soup = BeautifulSoup(html, "lxml")
        results: list[tuple[str, str]] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=True):
            href: str = a["href"].strip()
            if "/Home/CourseDates/" not in href:
                continue
            name = a.get_text(strip=True)
            if not name:
                continue
            # Build absolute URL
            if href.startswith("http"):
                abs_url = href
            else:
                abs_url = BOOKING_ROOT + href
            if abs_url not in seen:
                seen.add(abs_url)
                results.append((name, abs_url))

        return results

    def _parse_course_page(
        self,
        html: str,
        page_url: str,
        course_name: str,
        provider: dict,
    ) -> list[Offering]:
        """Parse available session rows from a single CourseDates page."""
        soup = BeautifulSoup(html, "lxml")
        now = datetime.now(timezone.utc).isoformat()

        # Determine course_id from course title
        course_id = _course_id_from_text(course_name)
        if not course_id:
            logger.debug(
                "FireAid: cannot map course_id for %r (%s)", course_name, page_url
            )
            return []

        # Locate the Available Dates section — it's a <ul> under an <h2>Available Dates</h2>
        dates_h2 = None
        for h2 in soup.find_all("h2"):
            if "available dates" in h2.get_text(strip=True).lower():
                dates_h2 = h2
                break

        if not dates_h2:
            logger.debug("FireAid: no 'Available Dates' heading found at %s", page_url)
            return []

        ul = dates_h2.find_next("ul")
        if not ul:
            logger.debug("FireAid: no <ul> after Available Dates at %s", page_url)
            return []

        offerings: list[Offering] = []
        seen_dates: set[str] = set()

        for li in ul.find_all("li", recursive=False):
            # Availability label
            avail_label = None
            label_span = li.find("span", class_="u-label")
            if label_span:
                raw_label = label_span.get_text(strip=True).lower()
                avail_label = _AVAIL_MAP.get(raw_label, raw_label)

            # Skip fully booked sessions
            if avail_label == "full":
                continue

            # Date and price from the tooltip span
            tooltip_span = li.find("span", attrs={"data-toggle": "tooltip"})
            if not tooltip_span:
                continue
            span_text = tooltip_span.get_text(" ", strip=True)

            # Extract start/end dates  (DD/MM/YYYY)
            dates_found = _DATE_RE.findall(span_text)
            if not dates_found:
                continue
            try:
                start_iso = datetime.strptime(dates_found[0], "%d/%m/%Y").date().isoformat()
            except ValueError:
                continue
            try:
                end_iso = (
                    datetime.strptime(dates_found[1], "%d/%m/%Y").date().isoformat()
                    if len(dates_found) > 1
                    else start_iso
                )
            except ValueError:
                end_iso = start_iso

            if start_iso in seen_dates:
                continue
            seen_dates.add(start_iso)

            # Price
            price: float | None = None
            price_m = _PRICE_RE.search(span_text)
            if price_m:
                try:
                    price = float(price_m.group(1))
                except ValueError:
                    pass

            # Duration in days (inclusive)
            try:
                dur = (
                    datetime.fromisoformat(end_iso) - datetime.fromisoformat(start_iso)
                ).days + 1
            except Exception:
                dur = None

            offerings.append(
                Offering(
                    id=f"{course_id}-fire-aid-{start_iso}",
                    course_id=course_id,
                    provider_id=provider["id"],
                    start_date=start_iso,
                    end_date=end_iso,
                    timezone="Europe/London",
                    duration_days=float(dur) if dur is not None else None,
                    price=price,
                    currency="GBP",
                    vat_included=True,
                    delivery_format="in_person",
                    availability=avail_label,
                    booking_url=safe_url(page_url),
                    source_url=page_url,
                    last_verified=now,
                    freshness_status="verified",
                )
            )

        logger.info(
            "FireAid: %d offerings for course_id=%s (%s)",
            len(offerings),
            course_id,
            page_url,
        )
        return offerings
