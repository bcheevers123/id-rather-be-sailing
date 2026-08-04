"""3T Training Services adapter.

Scrapes https://www.3tglobal.com/training-services/courses/?cat=1962 using
Playwright (JS-rendered listing) to discover individual STCW course pages,
then visits each page to extract scheduled dates, locations, and prices.

Strategy:
1. Load the category listing page via Playwright.
2. Collect links to individual course pages.
3. For each STCW-relevant course, load the course page and parse the schedule.
4. Return one Offering per date row found.
"""
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from pipeline.adapters.base import Offering
from pipeline.adapters.playwright_base import PlaywrightAdapter
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

LISTING_URL = "https://www.3tglobal.com/training-services/courses/?cat=1962"
BASE_URL = "https://www.3tglobal.com"

# Keywords in course title/URL → canonical course_id.
# Evaluated in order; first match wins.
_COURSE_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bpscrb\b|survival\s+craft", re.I), "pscrb"),
    (re.compile(r"\baff\b|advanced\s+fire", re.I), "aff"),
    (re.compile(r"\bpssr\b|personal\s+safety\s+(?:and\s+)?social", re.I), "pssr"),
    (re.compile(r"\bfpff\b|fire\s+prev(?:ention)?|fire\s+fight", re.I), "fpff"),
    (re.compile(r"\befa\b|elementary\s+first\s+aid", re.I), "efa"),
    (re.compile(r"\bbst\b|basic\s+safety", re.I), "pst"),
    (re.compile(r"\bpst\b|personal\s+survival", re.I), "pst"),
]

# Matches GBP price strings like "£395", "£1,200.00", "395.00"
_PRICE_RE = re.compile(r"[£\xA3]\s*([\d,]+(?:\.\d{2})?)")

# Matches ISO or common date strings
_DATE_PATTERNS = [
    re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})\b"),   # 12 January 2026
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),                   # 2026-01-12
    re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b"),                   # 12/01/2026
]


def _identify_course(text: str) -> str | None:
    """Return canonical course_id from title/URL text, or None if not STCW."""
    for pattern, course_id in _COURSE_MAP:
        if pattern.search(text):
            return course_id
    return None


def _parse_date(raw: str) -> str | None:
    """Parse a date string to ISO YYYY-MM-DD, or return None on failure."""
    raw = raw.strip()
    if not raw:
        return None

    # ISO format
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date().isoformat()
        except ValueError:
            pass

    # DD/MM/YYYY
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", raw)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).date().isoformat()
        except ValueError:
            pass

    # Try dateutil as fallback
    try:
        from dateutil import parser as dateutil_parser
        return dateutil_parser.parse(raw, fuzzy=True).date().isoformat()
    except Exception:
        return None


def _extract_price(text: str) -> float | None:
    """Extract first GBP price from a block of text, or None."""
    m = _PRICE_RE.search(text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


class ThreeTAdapter(PlaywrightAdapter):
    """Fetches STCW course offerings from 3T Training Services."""

    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        try:
            return self._fetch(provider)
        except Exception as e:
            logger.warning("ThreeT adapter unexpected error: %s", e)
            return []

    def _fetch(self, provider: dict) -> list[Offering]:
        # Step 1: load the listing page
        html = self.fetch_rendered(
            LISTING_URL,
            wait_selector=None,
            timeout=30000,
        )
        if not html:
            logger.warning("ThreeT: could not load listing page")
            return []

        # Step 2: discover course page links
        try:
            course_links = _extract_course_links(html)
        except Exception as e:
            logger.warning("ThreeT: listing parse failed: %s", e)
            return []

        if not course_links:
            logger.warning("ThreeT: no course links found on listing page")
            return []

        # Step 3: scrape each course page
        all_offerings: list[Offering] = []
        now = datetime.now(timezone.utc).isoformat()

        for url, title_hint in course_links:
            # Quick pre-filter: skip if URL + title hint clearly not STCW
            combined = f"{url} {title_hint}"
            course_id_hint = _identify_course(combined)
            if course_id_hint is None:
                logger.debug("ThreeT: skipping non-STCW link %s", url)
                continue

            page_html = self.fetch_rendered(url, wait_selector=None, timeout=30000)
            if not page_html:
                logger.warning("ThreeT: could not load course page %s", url)
                continue

            try:
                offerings = _parse_course_page(page_html, url, provider, now)
                all_offerings.extend(offerings)
            except Exception as e:
                logger.warning("ThreeT: parse failed for %s: %s", url, e)

        logger.info(
            "ThreeT adapter extracted %d offerings across %d course pages",
            len(all_offerings),
            len(course_links),
        )
        return all_offerings


def _extract_course_links(html: str) -> list[tuple[str, str]]:
    """Return list of (absolute_url, title_text) for course links on the listing page."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("ThreeT: beautifulsoup4 not installed")
        return []

    soup = BeautifulSoup(html, "lxml")
    seen: set[str] = set()
    results: list[tuple[str, str]] = []

    for a in soup.find_all("a", href=True):
        href: str = a["href"].strip()
        # 3T course pages live under /training-services/courses/ with a slug
        if "/training-services/courses/" not in href:
            continue
        # Build absolute URL
        abs_url = urljoin(BASE_URL, href).rstrip("/")
        # Skip the listing page itself (has ?cat= or ends at /courses/)
        if "?cat=" in abs_url or abs_url.rstrip("/").endswith("/courses"):
            continue
        if not abs_url.startswith("http"):
            continue
        if abs_url in seen:
            continue
        seen.add(abs_url)
        title_text = a.get_text(strip=True)
        results.append((abs_url, title_text))

    return results


def _parse_course_page(
    html: str,
    page_url: str,
    provider: dict,
    now: str,
) -> list[Offering]:
    """Parse a single 3T course page and return Offering objects."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    soup = BeautifulSoup(html, "lxml")

    # Identify course from title and URL
    title_tag = soup.find("h1") or soup.find("title")
    title_text = title_tag.get_text(strip=True) if title_tag else ""
    combined = f"{page_url} {title_text}"
    course_id = _identify_course(combined)
    if course_id is None:
        logger.debug("ThreeT: not an STCW course: %s", page_url)
        return []

    offerings: list[Offering] = []
    seen: set[str] = set()

    # Strategy A: find a schedule table with date/location columns
    schedule_table = _find_schedule_table(soup)
    if schedule_table is not None:
        offerings = _parse_schedule_table(
            schedule_table, course_id, page_url, provider, now, seen
        )

    # Strategy B: if no table found, scan for date-like rows in any container
    if not offerings:
        offerings = _scan_for_dates(soup, course_id, page_url, provider, now, seen)

    return offerings


def _find_schedule_table(soup):
    """Return the first table that looks like a course schedule."""
    for table in soup.find_all("table"):
        text = table.get_text(" ", strip=True).lower()
        # Look for date/location keywords
        if any(kw in text for kw in ("date", "start", "location", "venue")):
            return table
    return None


def _parse_schedule_table(
    table,
    course_id: str,
    page_url: str,
    provider: dict,
    now: str,
    seen: set,
) -> list[Offering]:
    """Extract offerings from a schedule table."""
    offerings: list[Offering] = []
    rows = table.find_all("tr")

    # Detect column positions from header row
    start_col = end_col = loc_col = price_col = None
    header_row = rows[0] if rows else None

    if header_row:
        headers = [th.get_text(strip=True).lower() for th in header_row.find_all(["th", "td"])]
        for i, h in enumerate(headers):
            if "start" in h or ("date" in h and start_col is None):
                start_col = i
            elif "end" in h or "finish" in h:
                end_col = i
            elif "location" in h or "venue" in h or "centre" in h:
                loc_col = i
            elif "price" in h or "cost" in h or "fee" in h or "£" in h:
                price_col = i

    data_rows = rows[1:] if header_row else rows

    for row in data_rows:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        cell_texts = [c.get_text(strip=True) for c in cells]

        # Skip header-like rows
        row_lower = " ".join(cell_texts).lower()
        if "start" in row_lower and "date" in row_lower and len(cell_texts) <= 2:
            continue

        # Extract start date
        start_date_iso: str | None = None
        end_date_iso: str | None = None
        location: str | None = None
        price: float | None = None

        if start_col is not None and start_col < len(cell_texts):
            start_date_iso = _parse_date(cell_texts[start_col])
        if end_col is not None and end_col < len(cell_texts):
            end_date_iso = _parse_date(cell_texts[end_col])
        if loc_col is not None and loc_col < len(cell_texts):
            location = cell_texts[loc_col] or None
        if price_col is not None and price_col < len(cell_texts):
            price = _extract_price(cell_texts[price_col])

        # Fallback: scan all cells for dates if column positions not identified
        if start_date_iso is None:
            for ct in cell_texts:
                d = _parse_date(ct)
                if d:
                    start_date_iso = d
                    break

        if start_date_iso is None:
            continue

        # Fallback: scan all cells for price
        if price is None:
            price = _extract_price(row.get_text())

        # Fallback: scan all cells for location (non-date, non-price, non-empty)
        if location is None:
            for ct in cell_texts:
                if ct and not _parse_date(ct) and not _PRICE_RE.search(ct):
                    location = ct
                    break

        if end_date_iso is None:
            end_date_iso = start_date_iso

        offering_id = f"{course_id}-3t-{provider['id']}-{start_date_iso}"
        if offering_id in seen:
            continue
        seen.add(offering_id)

        # Build availability string including location
        availability = location if location else None

        offerings.append(Offering(
            id=offering_id,
            course_id=course_id,
            provider_id=provider["id"],
            start_date=start_date_iso,
            end_date=end_date_iso,
            timezone="Europe/London",
            duration_days=None,
            price=price,
            currency="GBP" if price is not None else None,
            vat_included=None,
            delivery_format="in_person",
            availability=availability,
            booking_url=safe_url(page_url),
            source_url=page_url,
            last_verified=now,
            freshness_status="verified",
        ))

    return offerings


def _scan_for_dates(
    soup,
    course_id: str,
    page_url: str,
    provider: dict,
    now: str,
    seen: set,
) -> list[Offering]:
    """Fallback: scan the entire page for date patterns when no table is found."""
    offerings: list[Offering] = []
    date_re = re.compile(
        r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})\b"
        r"|\b(\d{4})-(\d{2})-(\d{2})\b"
        r"|\b(\d{1,2})/(\d{1,2})/(\d{4})\b"
    )

    # Work through paragraphs, divs, list items that contain date content
    for el in soup.find_all(["p", "li", "div", "span", "td"]):
        text = el.get_text(strip=True)
        if not date_re.search(text):
            continue

        start_date_iso = _parse_date(text)
        if not start_date_iso:
            continue

        # Try to find location nearby (parent or sibling text)
        location: str | None = None
        parent = el.parent
        if parent:
            sibling_texts = [
                s.get_text(strip=True)
                for s in parent.find_all(["p", "li", "div", "span", "td"])
                if s is not el and s.get_text(strip=True)
            ]
            for st in sibling_texts:
                if st and not date_re.search(st) and not _PRICE_RE.search(st):
                    # Heuristic: location text is short
                    if len(st) < 80:
                        location = st
                        break

        price = _extract_price(text)
        if price is None and parent:
            price = _extract_price(parent.get_text())

        offering_id = f"{course_id}-3t-{provider['id']}-{start_date_iso}"
        if offering_id in seen:
            continue
        seen.add(offering_id)

        offerings.append(Offering(
            id=offering_id,
            course_id=course_id,
            provider_id=provider["id"],
            start_date=start_date_iso,
            end_date=start_date_iso,
            timezone="Europe/London",
            duration_days=None,
            price=price,
            currency="GBP" if price is not None else None,
            vat_included=None,
            delivery_format="in_person",
            availability=location,
            booking_url=safe_url(page_url),
            source_url=page_url,
            last_verified=now,
            freshness_status="verified",
        ))

    return offerings
