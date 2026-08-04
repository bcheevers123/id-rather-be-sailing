"""University of Trinidad and Tobago (UTT) Maritime Studies adapter.

Scrapes the UTT STCW short-course listing page to discover individual course
pages, then parses each for start dates.

Date format on course pages:  "Start Date: Feb 27, 2023"  or  "Dates: TBA"
Most courses currently show "TBA"; the adapter silently skips those rows and
returns an empty list for them — this is expected behaviour, not a bug.

robots.txt: ClaudeBot is explicitly allowed.
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

BASE_URL = "https://utt.edu.tt"
LISTING_URL = f"{BASE_URL}/?wk=9&maritime_courses=1&ck=1"

# Maps keywords found in course titles to normalised course IDs.
# Checked in order — first match wins.
_COURSE_ID_MAP: list[tuple[re.Pattern, str]] = [
    # Basic Safety bundle (PST + FPFF + EFA + PSSR in one course at UTT)
    (re.compile(r"proficiency in basic safety\b", re.I), "pst"),
    (re.compile(r"updated proficiency in basic safety", re.I), "pst"),
    (re.compile(r"personal.survival.techniques|[^a-z]pst[^a-z]", re.I), "pst"),
    (re.compile(r"fire.prevention|[^a-z]fpff[^a-z]", re.I), "fpff"),
    (re.compile(r"elementary.first.aid|[^a-z]efa[^a-z]", re.I), "efa"),
    (re.compile(r"personal.safety.and.social|[^a-z]pssr[^a-z]", re.I), "pssr"),
    (re.compile(r"proficiency in survival craft|[^a-z]pscrb[^a-z]", re.I), "pscrb"),
    (re.compile(r"advanced.fire.fighting|[^a-z]aff[^a-z]", re.I), "aff"),
    (re.compile(r"medical.first.aid|[^a-z]mfa[^a-z]", re.I), "mfa"),
    # Medical Care (management level)
    (re.compile(r"medical.care|[^a-z]mc[^a-z]", re.I), "mc"),
    # Crisis Management / Human Element → management certificate
    (re.compile(r"crisis.management|human.element.leadership", re.I), "mc"),
    (re.compile(r"fast.rescue.boat|[^a-z]frb[^a-z]", re.I), "frb"),
]

# "Start Date: Feb 27, 2023"  or  "Dates\nStart Date: Feb 27, 2023"
_DATE_RE = re.compile(
    r"Start\s+Date[:\s]+([A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4})",
    re.IGNORECASE,
)

# Duration pattern: "5 days" / "4 DAYS" / "1 Day"
_DURATION_RE = re.compile(r"(\d+(?:\.\d+)?)\s+day", re.IGNORECASE)


def _course_id_from_text(text: str) -> str | None:
    """Return a course ID by matching text against the keyword map."""
    padded = f" {text} "
    for pattern, course_id in _COURSE_ID_MAP:
        if pattern.search(padded):
            return course_id
    return None


def _parse_date(raw: str) -> str | None:
    """Parse 'Feb 27, 2023' or 'Feb 27 2023' into ISO date string."""
    raw = raw.strip().replace(",", "")
    for fmt in ("%b %d %Y", "%B %d %Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


class UttAdapter(BaseAdapter):
    """Adapter for UTT Maritime Studies STCW short courses."""

    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        # Step 1: fetch the course listing page
        try:
            resp = session.get(LISTING_URL, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("UTT listing fetch failed: %s", e)
            return []
        time.sleep(2)

        # Step 2: extract course page links
        try:
            course_links = self._extract_course_links(resp.text)
        except Exception as e:
            logger.warning("UTT listing parse failed: %s", e)
            return []

        if not course_links:
            logger.warning("UTT: no course links found on listing page")
            return []

        # Step 3: scrape each course page
        all_offerings: list[Offering] = []
        for name, url in course_links:
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as e:
                logger.warning("UTT course fetch failed %s: %s", url, e)
                time.sleep(2)
                continue
            time.sleep(2)
            try:
                offerings = self._parse_course_page(resp.text, name, url, provider)
                all_offerings.extend(offerings)
            except Exception as e:
                logger.warning("UTT course parse failed %s: %s", url, e)

        logger.info("UTT adapter: %d offerings total", len(all_offerings))
        return all_offerings

    def _extract_course_links(self, html: str) -> list[tuple[str, str]]:
        """Return (name, absolute_url) pairs for individual course pages."""
        soup = BeautifulSoup(html, "lxml")
        links: list[tuple[str, str]] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=True):
            href: str = a["href"].strip()
            if "maritime_course_key=" not in href:
                continue
            name = a.get_text(" ", strip=True)
            # Build absolute URL
            if href.startswith("http"):
                abs_url = href
            elif href.startswith("/"):
                abs_url = BASE_URL + href
            else:
                abs_url = BASE_URL + "/" + href
            if abs_url not in seen:
                seen.add(abs_url)
                links.append((name, abs_url))

        return links

    def _parse_course_page(
        self, html: str, link_name: str, page_url: str, provider: dict
    ) -> list[Offering]:
        """Parse start dates from a single UTT STCW course page."""
        soup = BeautifulSoup(html, "lxml")
        now = datetime.now(timezone.utc).isoformat()

        # Determine course ID from page heading or link name
        h1 = soup.find("h1") or soup.find("h2")
        heading_text = h1.get_text(" ", strip=True) if h1 else ""
        course_id = (
            _course_id_from_text(heading_text)
            or _course_id_from_text(link_name)
            or _course_id_from_text(page_url)
        )
        if not course_id:
            logger.debug("UTT: could not determine course_id for %s", page_url)
            return []

        # Parse duration
        page_text = soup.get_text(" ", strip=True)
        duration_days: float | None = None
        dm = _DURATION_RE.search(page_text)
        if dm:
            try:
                duration_days = float(dm.group(1))
            except ValueError:
                pass

        # Find all "Start Date: ..." occurrences
        offerings: list[Offering] = []
        seen_dates: set[str] = set()

        for m in _DATE_RE.finditer(page_text):
            raw_date = m.group(1)
            start_iso = _parse_date(raw_date)
            if not start_iso or start_iso in seen_dates:
                continue
            seen_dates.add(start_iso)

            # Compute end date from duration
            if duration_days is not None:
                try:
                    from datetime import timedelta
                    end_dt = datetime.fromisoformat(start_iso) + timedelta(days=duration_days - 1)
                    end_iso = end_dt.date().isoformat()
                except Exception:
                    end_iso = start_iso
            else:
                end_iso = start_iso

            offerings.append(
                Offering(
                    id=f"{course_id}-utt-{start_iso}",
                    course_id=course_id,
                    provider_id=provider["id"],
                    start_date=start_iso,
                    end_date=end_iso,
                    timezone="America/Port_of_Spain",
                    duration_days=duration_days,
                    price=None,
                    currency=None,
                    vat_included=None,
                    delivery_format="in_person",
                    availability=None,
                    booking_url=safe_url(page_url),
                    source_url=page_url,
                    last_verified=now,
                    freshness_status="verified",
                )
            )

        logger.info(
            "UTT: %d offerings for course_id=%s (%s)",
            len(offerings),
            course_id,
            page_url,
        )
        return offerings
