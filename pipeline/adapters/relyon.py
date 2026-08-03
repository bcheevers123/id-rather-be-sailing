"""RelyOn Nutec adapter.

Scrapes https://shop.relyon.com/ — a JS-rendered booking platform — for
STCW/MCA maritime course dates at UK locations.

Location → provider_id mapping:
    Aberdeen  → relyon-nutec-aberdeen
    Glasgow   → relyon-glasgow
    Liverpool → relyon-liverpool
    Teesside  → relyon-nutec-teesside

Unknown locations fall back to ``relyon-nutec-aberdeen`` with the raw
location name surfaced in the ``availability`` field.
"""
import logging
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from pipeline.adapters.base import Offering
from pipeline.adapters.playwright_base import PlaywrightAdapter
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

BASE_URL = "https://shop.relyon.com"
SHOP_URL = BASE_URL + "/"

# ------------------------------------------------------------------
# Location → provider_id mapping
# ------------------------------------------------------------------
_LOCATION_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"aberdeen", re.I), "relyon-nutec-aberdeen"),
    (re.compile(r"glasgow", re.I), "relyon-glasgow"),
    (re.compile(r"liverpool", re.I), "relyon-liverpool"),
    (re.compile(r"teesside|tees", re.I), "relyon-nutec-teesside"),
]

_FALLBACK_PROVIDER_ID = "relyon-nutec-aberdeen"

# ------------------------------------------------------------------
# Course keyword → course_id mapping (checked in order)
# ------------------------------------------------------------------
_COURSE_ID_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"personal.survival.techniques|[^a-z]pst[^a-z]", re.I), "pst"),
    (re.compile(r"elementary.first.aid|[^a-z]efa[^a-z]", re.I), "efa"),
    (re.compile(r"fire.prevention|[^a-z]fpff[^a-z]", re.I), "fpff"),
    (re.compile(r"personal.safety|[^a-z]pssr[^a-z]", re.I), "pssr"),
    (re.compile(r"proficiency.in.survival.craft|[^a-z]pscrb[^a-z]", re.I), "pscrb"),
    (re.compile(r"advanced.fire.fighting|[^a-z]aff[^a-z]", re.I), "aff"),
]

# Date patterns: "12 Jan 2026", "12/01/2026", "2026-01-12"
_DATE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})\b"), "dmy_text"),
    (re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b"), "dmy_slash"),
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), "iso"),
]

_PRICE_RE = re.compile(r"£\s*([\d,]+(?:\.\d{2})?)")
_SPACES_RE = re.compile(r"(\d+)\s*(?:spaces?|places?|available)", re.I)

_MONTH_NAMES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}


def _parse_date(text: str) -> str | None:
    """Return ISO date string from various date formats, or None."""
    text = text.strip()
    for pattern, fmt in _DATE_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        try:
            if fmt == "dmy_text":
                day, month_str, year = int(m.group(1)), m.group(2).lower(), int(m.group(3))
                month = _MONTH_NAMES.get(month_str[:3])
                if not month:
                    continue
                return f"{year:04d}-{month:02d}-{day:02d}"
            elif fmt == "dmy_slash":
                day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
                return f"{year:04d}-{month:02d}-{day:02d}"
            elif fmt == "iso":
                return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        except (ValueError, AttributeError):
            continue
    return None


def _provider_id_from_location(location: str) -> str:
    """Map a location string to a provider_id."""
    for pattern, provider_id in _LOCATION_MAP:
        if pattern.search(location):
            return provider_id
    return _FALLBACK_PROVIDER_ID


def _course_id_from_text(text: str) -> str | None:
    """Return a course ID by matching text against the keyword map."""
    padded = f" {text} "
    for pattern, course_id in _COURSE_ID_MAP:
        if pattern.search(padded):
            return course_id
    return None


def _location_slug(location: str) -> str:
    """Convert a location name to a URL-safe slug."""
    return re.sub(r"[^a-z0-9]+", "-", location.lower()).strip("-") or "unknown"


class RelyOnAdapter(PlaywrightAdapter):
    """Adapter for RelyOn Nutec's JS-rendered booking platform."""

    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        """Fetch maritime course offerings from shop.relyon.com.

        Although ``provider`` is a single provider dict, this adapter may
        emit offerings for multiple provider_ids by inspecting each
        offering's location.
        """
        try:
            return self._fetch_all(provider)
        except Exception as e:
            logger.warning("RelyOn adapter unexpected error: %s", e)
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_all(self, provider: dict) -> list[Offering]:
        now = datetime.now(timezone.utc).isoformat()
        all_offerings: list[Offering] = []

        # Step 1: load the homepage and look for a maritime/STCW section
        html = self.fetch_rendered(SHOP_URL, timeout=30000)
        if not html:
            logger.warning("RelyOn: could not load homepage")
            return []

        # Step 2: find course catalogue links from the homepage
        course_urls = self._find_course_urls(html)

        if not course_urls:
            # Fallback: try common catalogue paths
            for path in ["/courses", "/maritime", "/stcw", "/training"]:
                fallback_html = self.fetch_rendered(BASE_URL + path, timeout=20000)
                if fallback_html:
                    course_urls = self._find_course_urls(fallback_html)
                    if course_urls:
                        break

        if not course_urls:
            # Last resort: treat the homepage itself as the catalogue
            course_urls = [(SHOP_URL, html)]

        # Step 3: for each course URL, scrape date/location/price rows
        for url, page_html in course_urls:
            try:
                if page_html is None:
                    page_html = self.fetch_rendered(url, timeout=20000)
                if not page_html:
                    continue
                offerings = self._parse_course_page(page_html, url, now)
                all_offerings.extend(offerings)
            except Exception as e:
                logger.warning("RelyOn: error processing %s: %s", url, e)

        # Deduplicate by offering id
        seen_ids: set[str] = set()
        unique: list[Offering] = []
        for o in all_offerings:
            if o.id not in seen_ids:
                seen_ids.add(o.id)
                unique.append(o)

        logger.info("RelyOn adapter: %d unique offerings total", len(unique))
        return unique

    def _find_course_urls(self, html: str) -> list[tuple[str, None]]:
        """Return list of (absolute_url, None) tuples for maritime course pages."""
        soup = BeautifulSoup(html, "lxml")
        urls: list[tuple[str, None]] = []
        seen: set[str] = set()

        maritime_keywords = re.compile(
            r"stcw|pst|efa|fpff|pssr|pscrb|aff|maritime|survival|firefighting|"
            r"fire.prevention|elementary.first.aid|personal.safety|safety.sea",
            re.I,
        )

        for a in soup.find_all("a", href=True):
            href: str = a["href"].strip()
            link_text = a.get_text(" ", strip=True)

            # Only follow links that mention maritime/STCW subjects
            if not maritime_keywords.search(href) and not maritime_keywords.search(link_text):
                continue

            # Skip anchor-only links, mailto, tel
            if href.startswith(("#", "mailto:", "tel:")):
                continue

            # Build absolute URL
            if href.startswith("http"):
                abs_url = href
            elif href.startswith("/"):
                abs_url = BASE_URL + href
            else:
                abs_url = BASE_URL + "/" + href.lstrip("/")

            # Keep only URLs on the same domain
            if BASE_URL not in abs_url:
                continue

            if abs_url not in seen:
                seen.add(abs_url)
                urls.append((abs_url, None))

        return urls

    def _parse_course_page(
        self, html: str, page_url: str, now: str
    ) -> list[Offering]:
        """Parse a course page for date/location/price rows."""
        soup = BeautifulSoup(html, "lxml")

        # Determine course ID from page title or heading
        title_text = ""
        for tag in ["h1", "h2", "title"]:
            el = soup.find(tag)
            if el:
                title_text = el.get_text(" ", strip=True)
                break

        course_id = _course_id_from_text(title_text) or _course_id_from_text(page_url)
        if not course_id:
            logger.debug("RelyOn: could not determine course_id for %s", page_url)
            return []

        offerings: list[Offering] = []
        seen_keys: set[str] = set()

        # Strategy A: look for structured date rows in tables
        for row in soup.find_all("tr"):
            o = self._row_to_offering(row, course_id, page_url, now)
            if o and o.id not in seen_keys:
                seen_keys.add(o.id)
                offerings.append(o)

        # Strategy B: look for booking cards / list items containing dates
        if not offerings:
            for container in soup.find_all(
                ["div", "li", "article", "section"],
                class_=re.compile(
                    r"course|event|date|session|booking|card|item|schedule", re.I
                ),
            ):
                o = self._container_to_offering(container, course_id, page_url, now)
                if o and o.id not in seen_keys:
                    seen_keys.add(o.id)
                    offerings.append(o)

        return offerings

    def _row_to_offering(
        self, row, course_id: str, page_url: str, now: str
    ) -> "Offering | None":
        """Try to build an Offering from a table row. Returns None if insufficient data."""
        cells = row.find_all(["td", "th"])
        if not cells:
            return None

        row_text = " ".join(c.get_text(" ", strip=True) for c in cells)

        start_date = _parse_date(row_text)
        if not start_date:
            return None

        location = self._extract_location(row_text)
        price = self._extract_price(row_text)
        availability = self._extract_availability(row_text)

        provider_id = _provider_id_from_location(location) if location else _FALLBACK_PROVIDER_ID

        # If location didn't map to a known provider, surface it in availability
        if location and _provider_id_from_location(location) == _FALLBACK_PROVIDER_ID:
            known_cities = {"aberdeen", "glasgow", "liverpool", "teesside"}
            if not any(city in location.lower() for city in known_cities):
                avail_note = f"Location: {location}"
                availability = (
                    f"{availability}; {avail_note}" if availability else avail_note
                )

        loc_slug = _location_slug(location) if location else "uk"
        offering_id = f"{course_id}-relyon-{loc_slug}-{start_date}"

        # Find booking link within the row
        booking_url: str | None = None
        for a in row.find_all("a", href=True):
            href = a["href"].strip()
            if href and not href.startswith("#"):
                booking_url = href if href.startswith("http") else BASE_URL + href
                break

        return Offering(
            id=offering_id,
            course_id=course_id,
            provider_id=provider_id,
            start_date=start_date,
            end_date=start_date,
            timezone="Europe/London",
            duration_days=None,
            price=price,
            currency="GBP" if price is not None else None,
            vat_included=None,
            delivery_format="in_person",
            availability=availability,
            booking_url=safe_url(booking_url or page_url),
            source_url=page_url,
            last_verified=now,
            freshness_status="verified",
        )

    def _container_to_offering(
        self, container, course_id: str, page_url: str, now: str
    ) -> "Offering | None":
        """Try to build an Offering from a div/li/card container."""
        text = container.get_text(" ", strip=True)

        start_date = _parse_date(text)
        if not start_date:
            return None

        location = self._extract_location(text)
        price = self._extract_price(text)
        availability = self._extract_availability(text)

        provider_id = _provider_id_from_location(location) if location else _FALLBACK_PROVIDER_ID

        if location and _provider_id_from_location(location) == _FALLBACK_PROVIDER_ID:
            known_cities = {"aberdeen", "glasgow", "liverpool", "teesside"}
            if not any(city in location.lower() for city in known_cities):
                avail_note = f"Location: {location}"
                availability = (
                    f"{availability}; {avail_note}" if availability else avail_note
                )

        loc_slug = _location_slug(location) if location else "uk"
        offering_id = f"{course_id}-relyon-{loc_slug}-{start_date}"

        booking_url: str | None = None
        for a in container.find_all("a", href=True):
            href = a["href"].strip()
            if href and not href.startswith("#"):
                booking_url = href if href.startswith("http") else BASE_URL + href
                break

        return Offering(
            id=offering_id,
            course_id=course_id,
            provider_id=provider_id,
            start_date=start_date,
            end_date=start_date,
            timezone="Europe/London",
            duration_days=None,
            price=price,
            currency="GBP" if price is not None else None,
            vat_included=None,
            delivery_format="in_person",
            availability=availability,
            booking_url=safe_url(booking_url or page_url),
            source_url=page_url,
            last_verified=now,
            freshness_status="verified",
        )

    # ------------------------------------------------------------------
    # Field extraction helpers
    # ------------------------------------------------------------------

    def _extract_location(self, text: str) -> str | None:
        """Extract a location/venue name from a block of text."""
        # Named UK cities relevant to RelyOn
        city_pattern = re.compile(
            r"\b(Aberdeen|Glasgow|Liverpool|Teesside|Middlesbrough|"
            r"Hartlepool|Stockton|Newcastle|Edinburgh|Dundee)\b",
            re.I,
        )
        m = city_pattern.search(text)
        if m:
            return m.group(1)

        # Generic "Location: Foo" or "Venue: Foo" labels
        label_pattern = re.compile(
            r"(?:location|venue|centre|center)\s*[:\-]\s*([A-Za-z][A-Za-z\s\-]{1,40})",
            re.I,
        )
        m2 = label_pattern.search(text)
        if m2:
            return m2.group(1).strip()

        return None

    def _extract_price(self, text: str) -> float | None:
        """Extract a GBP price from text. Returns None if not found."""
        m = _PRICE_RE.search(text)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                pass
        return None

    def _extract_availability(self, text: str) -> str | None:
        """Extract availability description (e.g. '5 spaces') from text."""
        m = _SPACES_RE.search(text)
        if m:
            return m.group(0).strip()
        # Check for "fully booked" / "sold out"
        if re.search(r"fully.booked|sold.out|no.places|no.spaces", text, re.I):
            return "Fully booked"
        return None
