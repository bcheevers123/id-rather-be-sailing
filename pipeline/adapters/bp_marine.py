"""B.P. Marine Academy (India) adapter.

The booking system lives at https://booking.bpmarine.in/GenericScreen/BookSelectedCourse.aspx
It is an ASP.NET WebForms page with a sidebar DataList that shows upcoming course offers.

Strategy:
  1. GET the booking page to obtain the initial VIEWSTATE / EVENTVALIDATION tokens.
  2. POST back with __EVENTTARGET set to the "View More" link control so the server
     expands the full offers list (default shows only ~6; View More expands to ~57+).
  3. Parse every <a class="offerlink"> element.  Each carries:
       refid    = category ID   (unused – for logging)
       refcourse= internal course ID  (used for course name matching)
       refbatch = batch ID  (used to construct a stable offering ID)
     The link text is  "<Course Name> - DD Mon YYYY"  e.g.
       "BST Basic Safety Training - 05 Aug 2026"
  4. Map course names to the project's canonical course IDs via keyword patterns.
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

BOOKING_URL = "https://booking.bpmarine.in/GenericScreen/BookSelectedCourse.aspx"

# ASP.NET control name for the "View More" LinkButton in the offers sidebar
_VIEW_MORE_TARGET = "ctl00$ctl00$ContentPlaceHolder1$myid"

# Maps keyword patterns to canonical course IDs.  Checked in order — first wins.
_COURSE_ID_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bpst\b|personal.survival.technique", re.I), "pst"),
    (re.compile(r"\bfpff\b|fire.prevention.and.fire.fighting", re.I), "fpff"),
    (re.compile(r"\befa\b|elementary.first.aid", re.I), "efa"),
    (re.compile(r"\bpssr\b|personal.safety.and.social.responsibilit", re.I), "pssr"),
    (re.compile(r"\bpscrb\b|proficiency.in.survival.craft", re.I), "pscrb"),
    (re.compile(r"\baff\b|advanced.fire.fighting", re.I), "aff"),
    (re.compile(r"\bmfa\b|medical.first.aid", re.I), "mfa"),
    (re.compile(r"\bmc\b|medical.care", re.I), "mc"),
    (re.compile(r"\bfrb\b|fast.rescue.boat", re.I), "frb"),
    # BST covers pst+fpff+efa+pssr combined — map to "bst" so callers can decide
    (re.compile(r"\bbst\b|basic.safety.training", re.I), "bst"),
]

# Date format used in offer text: "05 Aug 2026"
_DATE_RE = re.compile(r"\b(\d{1,2}\s+\w{3}\s+\d{4})\b")


def _course_id_from_text(text: str) -> str | None:
    padded = f" {text} "
    for pattern, course_id in _COURSE_ID_MAP:
        if pattern.search(padded):
            return course_id
    return None


def _parse_offer_date(text: str) -> str | None:
    """Return ISO date string from '05 Aug 2026' style text, or None."""
    m = _DATE_RE.search(text)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%d %b %Y").date().isoformat()
    except ValueError:
        return None


class BpMarineAdapter(BaseAdapter):
    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        # Step 1: GET initial page to obtain ASP.NET form tokens
        try:
            resp = session.get(BOOKING_URL, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("BPMarine: initial GET failed: %s", e)
            return []
        time.sleep(2)

        # Step 2: extract ASP.NET hidden fields
        try:
            tokens = self._extract_tokens(resp.text)
        except Exception as e:
            logger.warning("BPMarine: token extraction failed: %s", e)
            return []

        if not tokens.get("__VIEWSTATE"):
            logger.warning("BPMarine: no VIEWSTATE found — page structure may have changed")
            return []

        # Step 3: POST "View More" postback to expand the full offers list
        try:
            post_data = {
                "__EVENTTARGET": _VIEW_MORE_TARGET,
                "__EVENTARGUMENT": "",
                "__LASTFOCUS": "",
                **tokens,
            }
            resp2 = session.post(BOOKING_URL, data=post_data, timeout=30)
            resp2.raise_for_status()
        except Exception as e:
            logger.warning("BPMarine: View More POST failed: %s", e)
            return []
        time.sleep(2)

        # Step 4: parse the expanded offers list
        try:
            offerings = self._parse_offers(resp2.text, provider)
        except Exception as e:
            logger.warning("BPMarine: offer parse failed: %s", e)
            return []

        logger.info("BPMarine adapter: %d offerings total", len(offerings))
        return offerings

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_tokens(self, html: str) -> dict:
        """Return the ASP.NET hidden fields needed for postback."""
        soup = BeautifulSoup(html, "lxml")
        fields = ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"]
        result: dict = {}
        for field in fields:
            el = soup.find("input", {"name": field})
            if el:
                result[field] = el.get("value", "")
        return result

    def _parse_offers(self, html: str, provider: dict) -> list[Offering]:
        """Parse .offerlink anchors and return Offering objects."""
        soup = BeautifulSoup(html, "lxml")
        now = datetime.now(timezone.utc).isoformat()
        offerings: list[Offering] = []
        seen: set[str] = set()

        for a in soup.find_all("a", class_="offerlink"):
            text = a.get_text(strip=True)
            ref_batch = a.get("refbatch") or a.get("refBatch") or ""

            # Split on " - " to separate course name from date
            # e.g. "BST Basic Safety Training - 05 Aug 2026"
            parts = text.rsplit(" - ", 1)
            course_name = parts[0].strip() if len(parts) == 2 else text
            date_part = parts[1].strip() if len(parts) == 2 else text

            start_date = _parse_offer_date(date_part)
            if not start_date:
                logger.debug("BPMarine: could not parse date from %r", text)
                continue

            course_id = _course_id_from_text(course_name)
            if not course_id:
                logger.debug("BPMarine: no course_id for %r", course_name)
                continue

            # Stable dedup key: course_id + batch ID (batch ID is unique per date slot)
            dedup_key = f"{course_id}-{ref_batch}" if ref_batch else f"{course_id}-{start_date}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            offering_id = (
                f"{course_id}-bp-marine-{ref_batch}"
                if ref_batch
                else f"{course_id}-bp-marine-{start_date}"
            )

            offerings.append(
                Offering(
                    id=offering_id,
                    course_id=course_id,
                    provider_id=provider["id"],
                    start_date=start_date,
                    end_date=start_date,
                    timezone="Asia/Kolkata",
                    duration_days=None,
                    price=None,
                    currency=None,
                    vat_included=None,
                    delivery_format="in_person",
                    availability=None,
                    booking_url=safe_url(BOOKING_URL),
                    source_url=BOOKING_URL,
                    last_verified=now,
                    freshness_status="verified",
                )
            )

        return offerings
