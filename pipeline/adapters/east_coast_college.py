"""East Coast College (East Coast Training Academy) adapter.

The STCW/maritime short courses are listed on the sub-site
https://www.eastcoasttrainingacademy.co.uk/maritime/ (eastcoast.ac.uk
redirects maritime commercial training to ecdevelop.co.uk which itself
permanently redirects to eastcoasttrainingacademy.co.uk).

Course pages that have scheduled dates embed the date in every "Apply"
booking-link query-string as ``Course_Start_Date=DD/MM/YYYY``.  Pages
that have no public schedule show only an "Enquire Now" button and are
silently skipped.
"""
import logging
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

from pipeline.adapters.base import BaseAdapter, Offering
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; "
    "+https://github.com/bcheevers123/id-rather-be-sailing)"
)

BASE_URL = "https://www.eastcoasttrainingacademy.co.uk"
MARITIME_LISTING_URL = f"{BASE_URL}/maritime/"

# Maps keyword patterns in titles/URLs to normalised course IDs.
# Checked in order — first match wins.
_COURSE_ID_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"personal.survival.techniques|[^a-z]pst[^a-z]", re.I), "pst"),
    (re.compile(r"elementary.first.aid|[^a-z]efa[^a-z]", re.I), "efa"),
    (re.compile(r"fire.prevention.and.fire.fighting|[^a-z]fpff[^a-z]", re.I), "fpff"),
    (re.compile(r"personal.safety.and.social.responsibilities|[^a-z]pssr[^a-z]", re.I), "pssr"),
    (re.compile(r"proficiency.in.survival.craft|[^a-z]pscrb[^a-z]", re.I), "pscrb"),
    (re.compile(r"advanced.fire.fighting|[^a-z]aff[^a-z]", re.I), "aff"),
    (re.compile(r"medical.first.aid|[^a-z]mfa[^a-z]", re.I), "mfa"),
    (re.compile(r"medical.care.aboard|[^a-z]mc[^a-z]", re.I), "mc"),
    (re.compile(r"fast.rescue.boat|fast.rescue.craft|[^a-z]frb[^a-z]", re.I), "frb"),
]

# DD/MM/YYYY date pattern (used in booking link query params)
_DATE_RE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")

# Price pattern: £ sign (U+00A3) required, then digits
_PRICE_RE = re.compile(r"\xa3\s*([\d,]+(?:\.\d{2})?)")


def _course_id_from_text(text: str) -> str | None:
    """Return a normalised course ID by matching text against the keyword map."""
    padded = f" {text} "
    for pattern, course_id in _COURSE_ID_MAP:
        if pattern.search(padded):
            return course_id
    return None


def _parse_price(soup: BeautifulSoup) -> tuple[float | None, bool | None]:
    """Extract price and vat_included from the page body."""
    text = soup.get_text(" ", strip=True)
    # Look for price pattern near VAT indicator
    m = _PRICE_RE.search(text)
    if not m:
        return None, None
    price_str = m.group(1).replace(",", "")
    try:
        price = float(price_str)
    except ValueError:
        return None, None

    # Determine VAT inclusion
    # Grab a window of text around the match to check VAT indication
    start = max(0, m.start() - 5)
    end = min(len(text), m.end() + 30)
    window = text[start:end].lower()
    if "inc" in window or "including vat" in window:
        vat_included = True
    elif "exc" in window or "excluding vat" in window or "ex vat" in window:
        vat_included = False
    else:
        vat_included = None

    return price, vat_included


class EastCoastCollegeAdapter(BaseAdapter):
    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        # Step 1: fetch the maritime course listing page
        try:
            resp = session.get(MARITIME_LISTING_URL, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("EastCoastCollege listing fetch failed: %s", e)
            return []
        time.sleep(2)

        # Step 2: extract links to individual course pages
        try:
            course_links = self._extract_course_links(resp.text)
        except Exception as e:
            logger.warning("EastCoastCollege listing parse failed: %s", e)
            return []

        if not course_links:
            logger.warning("EastCoastCollege: no course links found on listing page")
            return []

        logger.info("EastCoastCollege: found %d course links", len(course_links))

        # Step 3: scrape each course page for dates
        all_offerings: list[Offering] = []
        for url in course_links:
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as e:
                logger.warning("EastCoastCollege course fetch failed %s: %s", url, e)
                time.sleep(2)
                continue
            time.sleep(2)
            try:
                offerings = self._parse_course_page(resp.text, url, provider)
                all_offerings.extend(offerings)
            except Exception as e:
                logger.warning("EastCoastCollege course parse failed %s: %s", url, e)

        logger.info(
            "EastCoastCollege adapter: %d offerings total", len(all_offerings)
        )
        return all_offerings

    def _extract_course_links(self, html: str) -> list[str]:
        """Return absolute URLs of individual course pages from the maritime listing."""
        soup = BeautifulSoup(html, "lxml")
        links: list[str] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=True):
            href: str = a["href"].strip()
            # Course pages live under /courses/ (not /course/ which are simulator sims)
            if "/courses/" not in href:
                continue
            # Build absolute URL
            if href.startswith("http"):
                abs_url = href
            elif href.startswith("/"):
                abs_url = BASE_URL + href
            else:
                abs_url = urljoin(MARITIME_LISTING_URL, href)
            # Only keep URLs on the same host
            if urlparse(abs_url).netloc != urlparse(BASE_URL).netloc:
                continue
            if abs_url not in seen:
                seen.add(abs_url)
                links.append(abs_url)

        return links

    def _parse_course_page(
        self, html: str, page_url: str, provider: dict
    ) -> list[Offering]:
        """Parse course dates from a single East Coast Training Academy course page.

        Dates are embedded in booking link query strings as Course_Start_Date=DD/MM/YYYY.
        Pages without public schedules use an "Enquire Now" button and have no such links.
        """
        soup = BeautifulSoup(html, "lxml")
        now = datetime.now(timezone.utc).isoformat()

        # Determine course ID from page title or URL
        title_tag = soup.find("h1") or soup.find("title")
        title_text = title_tag.get_text(" ", strip=True) if title_tag else ""
        course_id = _course_id_from_text(title_text) or _course_id_from_text(page_url)
        if not course_id:
            logger.debug("EastCoastCollege: unrecognised course at %s", page_url)
            return []

        price, vat_included = _parse_price(soup)

        offerings: list[Offering] = []
        seen_dates: set[str] = set()

        # Look for all links to /course-apply/ — each carries a date in query params
        for a in soup.find_all("a", href=True):
            href: str = a["href"]
            if "/course-apply/" not in href:
                continue

            # Build absolute URL for the booking link
            if href.startswith("http"):
                booking_abs = href
            elif href.startswith("/"):
                booking_abs = BASE_URL + href
            else:
                booking_abs = urljoin(page_url, href)

            # Parse query string for Course_Start_Date
            parsed = urlparse(booking_abs)
            qs = parse_qs(parsed.query)
            start_date_raw = qs.get("Course_Start_Date", [None])[0]
            end_date_raw = qs.get("Course_End_Date", [None])[0]

            if not start_date_raw:
                # Fallback: try to extract DD/MM/YYYY from the raw href
                m = _DATE_RE.search(href)
                if m:
                    start_date_raw = m.group(1)
                else:
                    continue

            # Parse start date
            try:
                start_date_iso = (
                    datetime.strptime(start_date_raw.strip(), "%d/%m/%Y").date().isoformat()
                )
            except ValueError:
                logger.debug(
                    "EastCoastCollege: unparseable date %r at %s", start_date_raw, page_url
                )
                continue

            # Parse end date (fall back to start date for 1-day courses)
            end_date_iso = start_date_iso
            if end_date_raw:
                try:
                    end_date_iso = (
                        datetime.strptime(end_date_raw.strip(), "%d/%m/%Y").date().isoformat()
                    )
                except ValueError:
                    pass

            if start_date_iso in seen_dates:
                continue
            seen_dates.add(start_date_iso)

            offerings.append(
                Offering(
                    id=f"{course_id}-east-coast-college-{start_date_iso}",
                    course_id=course_id,
                    provider_id=provider["id"],
                    start_date=start_date_iso,
                    end_date=end_date_iso,
                    timezone="Europe/London",
                    duration_days=None,
                    price=price,
                    currency="GBP",
                    vat_included=vat_included,
                    delivery_format="in_person",
                    availability=None,
                    booking_url=safe_url(booking_abs),
                    source_url=page_url,
                    last_verified=now,
                    freshness_status="verified",
                )
            )

        if offerings:
            logger.info(
                "EastCoastCollege: %d offerings for course_id=%s (%s)",
                len(offerings),
                course_id,
                page_url,
            )
        else:
            logger.debug(
                "EastCoastCollege: no dated offerings for course_id=%s (%s)",
                course_id,
                page_url,
            )

        return offerings
