"""iPowerboat Limited adapter.

iPowerboat Limited (Kinlochleven, Argyll & Bute) trades as SeaRegs Training Ltd.
The website https://www.ipowerboat.co.uk/ permanently redirects (HTTP 301) to
https://www.searegs.co.uk/, and course bookings are hosted on Arlo at
https://ipowerboat.arlo.co/w/upcoming/.

robots.txt on ipowerboat.arlo.co returns 404 (no restrictions), and the
Squarespace robots.txt on searegs.co.uk does not block /upcoming/ or any course
schedule paths.

Three provider IDs share this domain:
  - ipowerboat-limited          (Kinlochleven base)
  - ipowerboat-limited-2        (Kinlochleven base, duplicate MCA listing)
  - ipowerboat-limited-3        (Peripatetic / Multi-Site delivery)

All three share the same Arlo instance, so a single fetch call returns
offerings that span all delivery locations.  The caller (pipeline runner) is
responsible for deciding which provider ID to attach; we emit every offering
once tagged with provider["id"] as supplied.
"""
import logging
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup, Tag
from dateutil import parser as dateutil_parser

from pipeline.adapters.base import BaseAdapter, Offering
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; "
    "+https://github.com/bcheevers123/id-rather-be-sailing)"
)

ARLO_BASE = "https://ipowerboat.arlo.co"
UPCOMING_URL = f"{ARLO_BASE}/w/upcoming/"

# Maps course-name fragments to normalised course IDs (first match wins).
_COURSE_ID_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"personal.survival.techniques|[^a-z]pst[^a-z]", re.I), "pst"),
    (re.compile(r"fire.prevention.*fighting|fire.fighting|[^a-z]fpff[^a-z]", re.I), "fpff"),
    (re.compile(r"elementary.first.aid|[^a-z]efa[^a-z]", re.I), "efa"),
    (
        re.compile(
            r"personal.safety.and.social|[^a-z]pssr[^a-z]"
            r"|security.awareness|proficiency.in.security",
            re.I,
        ),
        "pssr",
    ),
    (re.compile(r"proficiency.in.survival.craft|survival.craft.*rescue|[^a-z]pscrb[^a-z]", re.I), "pscrb"),
    (re.compile(r"advanced.fire.fighting|[^a-z]aff[^a-z]", re.I), "aff"),
    (re.compile(r"medical.first.aid|[^a-z]mfa[^a-z]", re.I), "mfa"),
    (re.compile(r"medical.care[^a-z]|[^a-z]\bmc\b[^a-z]", re.I), "mc"),
    (re.compile(r"fast.rescue.boat|[^a-z]frb[^a-z]", re.I), "frb"),
]

# £170.00 or £ 170.00 (£ may appear as the unicode U+00A3 literal)
_PRICE_RE = re.compile(r"[££]\s*([\d,]+(?:\.\d{2})?)")

# Date range: "5 - 7 Aug 2026" or "5–7 Aug 2026"
_DATE_RANGE_RE = re.compile(
    r"(\d{1,2})\s*[-–]\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})"
)
# Single date: "Wed 5 Aug 2026" or "5 Aug 2026"
_SINGLE_DATE_RE = re.compile(
    r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)?\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})",
    re.I,
)


def _course_id_from_text(text: str) -> str | None:
    padded = f" {text} "
    for pattern, cid in _COURSE_ID_MAP:
        if pattern.search(padded):
            return cid
    return None


def _parse_date_text(text: str) -> tuple[str | None, str | None]:
    """Return (start_iso, end_iso) from a date string, or (None, None)."""
    m = _DATE_RANGE_RE.search(text)
    if m:
        day1, day2, month, year = m.group(1), m.group(2), m.group(3), m.group(4)
        try:
            start = dateutil_parser.parse(f"{day1} {month} {year}").date().isoformat()
            end = dateutil_parser.parse(f"{day2} {month} {year}").date().isoformat()
            return start, end
        except Exception:
            pass

    m = _SINGLE_DATE_RE.search(text)
    if m:
        day, month, year = m.group(1), m.group(2), m.group(3)
        try:
            iso = dateutil_parser.parse(f"{day} {month} {year}").date().isoformat()
            return iso, iso
        except Exception:
            pass

    return None, None


def _extract_price(text: str) -> tuple[float | None, bool | None]:
    m = _PRICE_RE.search(text)
    if not m:
        return None, None
    price = float(m.group(1).replace(",", ""))
    lower = text.lower()
    if "incl" in lower and "vat" in lower:
        vat = True
    elif "excl" in lower and "vat" in lower:
        vat = False
    else:
        vat = None
    return price, vat


def _extract_availability(text: str) -> str | None:
    lower = text.lower()
    if "sold out" in lower or "fully booked" in lower:
        return "Sold out"
    m = re.search(r"(\d+)\s+place", lower)
    if m:
        n = int(m.group(1))
        return f"{n} place{'s' if n != 1 else ''} remaining"
    if "limited" in lower:
        return "Limited places"
    if "available" in lower or "open" in lower:
        return "Available"
    return None


def _parse_card(card: Tag, now: str, provider: dict) -> Offering | None:
    """Parse one Arlo event card and return an Offering, or None if not STCW."""
    card_text = card.get_text(" ", strip=True)

    # Course name: prefer a labelled element, fall back to first heading or link
    name_tag = (
        card.find(class_=re.compile(r"event.name|course.name|event.title", re.I))
        or card.find("h2")
        or card.find("h3")
        or card.find("h4")
        or card.find("a", href=re.compile(r"/w/(?:events?|courses?)/", re.I))
    )
    course_name = name_tag.get_text(" ", strip=True) if name_tag else card_text[:80]

    course_id = _course_id_from_text(course_name) or _course_id_from_text(card_text)
    if not course_id:
        return None  # not an STCW/safety course we track

    # Dates
    date_tag = card.find(class_=re.compile(r"event.date|date.time|session.date", re.I))
    date_text = date_tag.get_text(" ", strip=True) if date_tag else card_text
    start_date, end_date = _parse_date_text(date_text)
    if not start_date:
        start_date, end_date = _parse_date_text(card_text)
    if not start_date:
        logger.debug("IpowerboatAdapter: could not parse date from card: %s", card_text[:120])
        return None

    # Price
    price, vat_included = _extract_price(card_text)

    # Availability
    avail_tag = card.find(class_=re.compile(r"availab|places|status", re.I))
    avail_text = avail_tag.get_text(" ", strip=True) if avail_tag else card_text
    availability = _extract_availability(avail_text)

    # Booking URL — prefer a direct event/course link
    link_tag = (
        card.find("a", href=re.compile(r"/w/(?:events?|courses?)/\d+", re.I))
        or card.find("a", href=re.compile(r"register|book", re.I))
    )
    raw_href: str | None = link_tag.get("href") if link_tag else None
    if raw_href and raw_href.startswith("/"):
        raw_href = ARLO_BASE + raw_href
    booking_url = safe_url(raw_href)

    offering_id = (
        f"{provider['id']}-ipowerboat-{course_id}-{start_date}"
    )[:80]

    return Offering(
        id=offering_id,
        course_id=course_id,
        provider_id=provider["id"],
        start_date=start_date,
        end_date=end_date or start_date,
        timezone="Europe/London",
        duration_days=None,
        price=price,
        currency="GBP" if price is not None else None,
        vat_included=vat_included,
        delivery_format="in_person",
        availability=availability,
        booking_url=booking_url,
        source_url=UPCOMING_URL,
        last_verified=now,
        freshness_status="verified",
    )


class IpowerboatAdapter(BaseAdapter):
    """Scrape STCW/safety course dates from iPowerboat Limited.

    iPowerboat trades as SeaRegs Training Ltd and hosts its public schedule on
    the Arlo platform at ipowerboat.arlo.co.  The /w/upcoming/ listing is
    server-side rendered and paginated (page-2, page-3 …).

    www.ipowerboat.co.uk permanently redirects to www.searegs.co.uk; neither
    domain's robots.txt restricts schedule paths.

    Returns one Offering per STCW/safety course date found.  Returns [] if the
    page cannot be fetched or contains no matching courses.
    """

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        offerings: list[Offering] = []
        seen_ids: set[str] = set()
        now = datetime.now(timezone.utc).isoformat()

        page = 1
        while True:
            url = UPCOMING_URL if page == 1 else f"{UPCOMING_URL}page-{page}/"
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning(
                    "IpowerboatAdapter: fetch failed (page %d) %s: %s", page, url, exc
                )
                break

            # Minimum 2-second delay between requests to the same domain
            time.sleep(2)

            try:
                page_offerings, has_more = self._parse_page(
                    resp.text, now, provider, seen_ids
                )
            except Exception as exc:
                logger.warning(
                    "IpowerboatAdapter: parse failed (page %d): %s", page, exc
                )
                break

            offerings.extend(page_offerings)

            if not has_more:
                break
            page += 1
            if page > 20:  # safety cap against infinite pagination
                logger.warning("IpowerboatAdapter: hit page cap (20), stopping")
                break

        logger.info(
            "IpowerboatAdapter: %d STCW offerings across %d page(s) for provider %s",
            len(offerings),
            page,
            provider.get("id"),
        )
        return offerings

    def _parse_page(
        self,
        html: str,
        now: str,
        provider: dict,
        seen_ids: set[str],
    ) -> tuple[list[Offering], bool]:
        """Parse one Arlo upcoming-courses page.

        Returns (offerings, has_next_page).
        """
        soup = BeautifulSoup(html, "lxml")

        # Arlo server-renders cards with class "event-card-container".
        # Fall back through progressively broader selectors.
        cards: list[Tag] = (
            soup.find_all("div", class_=re.compile(r"event.card", re.I))
            or soup.find_all("div", class_=re.compile(r"card.front", re.I))
            or soup.find_all("div", class_=re.compile(r"event.content", re.I))
            # Last resort: any short div containing a price and a year
            or [
                tag
                for tag in soup.find_all("div")
                if re.search(r"[££]", tag.get_text())
                and re.search(r"\b20\d\d\b", tag.get_text())
                and len(tag.get_text()) < 600
            ]
        )

        page_offerings: list[Offering] = []
        for card in cards:
            try:
                offering = _parse_card(card, now, provider)
            except Exception as exc:
                logger.debug("IpowerboatAdapter: card parse error: %s", exc)
                continue
            if offering is None:
                continue
            if offering.id in seen_ids:
                continue
            seen_ids.add(offering.id)
            page_offerings.append(offering)

        has_more = bool(
            soup.find("a", href=re.compile(r"/w/upcoming/page-\d+", re.I))
            or soup.find(string=re.compile(r"show more|next page", re.I))
        )

        return page_offerings, has_more
