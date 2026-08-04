"""NAFC Marine Centre / UHI Shetland adapter.

Scrapes the UHI Shetland upcoming-courses page for STCW maritime safety course
dates.

Page structure (static HTML, no JS required).  Each course lives in a
collapsible section:

    <div class="content-type-modifier--collapsible">
      <h2 class="content-type-modifier--collapsible__heading">
        <span>...</span>
        <span>Personal Survival Techniques</span>
      </h2>
      <div class="content-type--one-web-general-content ...">
        <!-- variant A: date in <li><strong> -->
        <ul>
          <li><strong>24-04-2025</strong></li>
          <li>08:00 - 18:00</li>
          <li>£220 per person</li>
        </ul>
        <p><a href="https://www.eventbrite.co.uk/...">Book ...</a></p>

        <!-- variant B: date in <p><strong>, price in following <ul> -->
        <p><strong>11-02-2025 to 12-02-2025</strong></p>
        <ul>
          <li>09:00 - 17:00</li>
          <li>£250 per person</li>
        </ul>
        <p><a href="...">Book ...</a></p>
      </div>
    </div>

Multi-date courses repeat the ul/p pattern, or use flex-cols columns.
Dates are DD-MM-YYYY.  A single date means start == end.
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

SOURCE_URL = (
    "https://www.shetland.uhi.ac.uk"
    "/business-consultancy-and-training"
    "/commercial-and-business-training/upcoming-courses/"
)

# Maps keywords in course headings to normalised course IDs.
# Checked in order — first match wins.
_COURSE_ID_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"personal\s+survival\s+tech|\bpst\b", re.I), "pst"),
    (re.compile(r"fire\s+prevention|fire\s+fighting|\bfpff\b", re.I), "fpff"),
    (re.compile(r"elementary\s+first\s+aid|\befa\b", re.I), "efa"),
    (re.compile(r"personal\s+safety\s+and\s+social|\bpssr\b", re.I), "pssr"),
    (re.compile(r"proficiency\s+in\s+survival\s+craft|\bpscrb\b", re.I), "pscrb"),
    (re.compile(r"advanced\s+fire\s+fighting|\baff\b", re.I), "aff"),
    (re.compile(r"medical\s+first\s+aid|\bmfa\b", re.I), "mfa"),
    (re.compile(r"medical\s+care|\bmc\b", re.I), "mc"),
    (re.compile(r"rescue\s+boat|\bfrb\b", re.I), "frb"),
]

# Matches either "DD-MM-YYYY" or "DD-MM-YYYY to DD-MM-YYYY"
_DATE_RANGE_RE = re.compile(
    r"(\d{2}-\d{2}-\d{4})"
    r"(?:\s+to\s+(\d{2}-\d{2}-\d{4}))?",
    re.I,
)

# Matches "£NNN" or "£NNN.NN" optionally followed by "per person"
_PRICE_RE = re.compile(r"£\s*(\d+(?:\.\d+)?)")


def _course_id_from_text(text: str) -> str | None:
    for pattern, course_id in _COURSE_ID_MAP:
        if pattern.search(text):
            return course_id
    return None


def _parse_date(raw: str) -> str | None:
    """Convert DD-MM-YYYY → ISO YYYY-MM-DD, or return None on failure."""
    try:
        return datetime.strptime(raw.strip(), "%d-%m-%Y").date().isoformat()
    except ValueError:
        return None


class NafcAdapter(BaseAdapter):
    """Adapter for NAFC Marine Centre / UHI Shetland short maritime courses."""

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        try:
            resp = session.get(SOURCE_URL, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("NAFC fetch failed: %s", e)
            return []
        time.sleep(2)

        try:
            offerings = self._parse_page(resp.text, provider)
        except Exception as e:
            logger.warning("NAFC parse failed: %s", e)
            return []

        logger.info("NAFC adapter: %d offerings total", len(offerings))
        return offerings

    def _parse_page(self, html: str, provider: dict) -> list[Offering]:
        soup = BeautifulSoup(html, "lxml")
        now = datetime.now(timezone.utc).isoformat()
        offerings: list[Offering] = []
        seen: set[str] = set()

        # Each course lives inside a collapsible <div>.  The section heading
        # is the last non-empty <span> child of the collapsible <h2>.
        collapsible_divs = soup.find_all(
            "div", class_=lambda c: c and "content-type-modifier--collapsible" in c
        )

        for section in collapsible_divs:
            heading_h2 = section.find(
                "h2", class_=lambda c: c and "collapsible__heading" in c
            )
            if not heading_h2:
                continue
            spans = [s.get_text(strip=True) for s in heading_h2.find_all("span") if s.get_text(strip=True)]
            course_name = spans[-1] if spans else heading_h2.get_text(" ", strip=True)

            course_id = _course_id_from_text(course_name)
            if not course_id:
                continue

            # The content div holds all date/price/booking nodes.
            content_div = section.find(
                "div", class_=lambda c: c and "one-web-general-content" in c
            )
            if not content_div:
                continue

            offerings.extend(
                self._extract_offerings(content_div, course_id, course_name, provider["id"], now, seen)
            )

        logger.debug("NAFC: %d total offerings parsed", len(offerings))
        return offerings

    def _extract_offerings(
        self,
        content_div,
        course_id: str,
        course_name: str,
        provider_id: str,
        now: str,
        seen: set[str],
    ) -> list[Offering]:
        """
        Walk direct children of content_div and collect date blocks.

        Two patterns occur:
          A) <ul> where the first <li><strong> contains the date(s).
          B) <p><strong>date</strong></p> followed by a <ul> with time/price.

        In both cases a <p><a href=...> booking link follows the block.
        """
        results: list[Offering] = []
        children = list(content_div.children)

        i = 0
        while i < len(children):
            node = children[i]
            if not hasattr(node, "name") or node.name is None:
                i += 1
                continue

            start_iso: str | None = None
            end_iso: str | None = None
            price: float | None = None
            currency: str | None = None
            booking_url: str | None = None

            if node.name == "ul":
                # Pattern A: first <li> has a <strong> with date(s);
                # subsequent <li>s may have the price.
                lis = node.find_all("li")
                for li in lis:
                    li_text = li.get_text(" ", strip=True)
                    m = _DATE_RANGE_RE.search(li_text)
                    if m and start_iso is None:
                        start_iso = _parse_date(m.group(1))
                        end_iso = _parse_date(m.group(2)) if m.group(2) else start_iso
                    pm = _PRICE_RE.search(li_text)
                    if pm and price is None:
                        try:
                            price = float(pm.group(1))
                            currency = "GBP"
                        except ValueError:
                            pass

                # Look ahead for a booking link in a <p> or direct <a>
                j = i + 1
                while j < len(children):
                    sib = children[j]
                    if not hasattr(sib, "name") or sib.name is None:
                        j += 1
                        continue
                    if sib.name == "ul":
                        break  # next date block
                    if sib.name in ("p", "a"):
                        a_tag = sib if sib.name == "a" else sib.find("a")
                        if a_tag and a_tag.get("href") and booking_url is None:
                            booking_url = safe_url(a_tag["href"])
                    j += 1

            elif node.name == "p":
                # Pattern B: <p><strong>DD-MM-YYYY...</strong></p>
                strong = node.find("strong")
                if not strong:
                    i += 1
                    continue
                p_text = strong.get_text(" ", strip=True)
                m = _DATE_RANGE_RE.search(p_text)
                if not m:
                    i += 1
                    continue
                start_iso = _parse_date(m.group(1))
                end_iso = _parse_date(m.group(2)) if m.group(2) else start_iso

                # Look ahead for <ul> (time/price) and booking link
                j = i + 1
                while j < len(children):
                    sib = children[j]
                    if not hasattr(sib, "name") or sib.name is None:
                        j += 1
                        continue
                    if sib.name == "ul" and price is None:
                        for li in sib.find_all("li"):
                            pm = _PRICE_RE.search(li.get_text(" ", strip=True))
                            if pm:
                                try:
                                    price = float(pm.group(1))
                                    currency = "GBP"
                                except ValueError:
                                    pass
                    if sib.name in ("p", "a"):
                        a_tag = sib if sib.name == "a" else sib.find("a")
                        if a_tag and a_tag.get("href") and booking_url is None:
                            booking_url = safe_url(a_tag["href"])
                    # Stop at the next date-bearing <p>
                    if sib.name == "p" and sib.find("strong"):
                        break
                    j += 1

            else:
                # flex-cols: recurse into each column
                if "flex-cols" in (node.get("class") or []):
                    for col in node.find_all("div", class_=lambda c: c and "flex-cols__col" in c):
                        results.extend(
                            self._extract_offerings(col, course_id, course_name, provider_id, now, seen)
                        )
                i += 1
                continue

            if start_iso:
                offering_id = f"{course_id}-nafc-{start_iso}"
                if offering_id not in seen:
                    seen.add(offering_id)
                    results.append(
                        Offering(
                            id=offering_id,
                            course_id=course_id,
                            provider_id=provider_id,
                            start_date=start_iso,
                            end_date=end_iso or start_iso,
                            timezone="Europe/London",
                            duration_days=None,
                            price=price,
                            currency=currency,
                            vat_included=None,
                            delivery_format="in_person",
                            availability=None,
                            booking_url=booking_url,
                            source_url=SOURCE_URL,
                            last_verified=now,
                            freshness_status="verified",
                        )
                    )

            i += 1

        return results
