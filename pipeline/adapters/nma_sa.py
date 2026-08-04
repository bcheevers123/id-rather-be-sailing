"""National Maritime Academy (NMA), Saudi Arabia — adapter.

Investigation notes (2026-08-04):
  - https://www.nma.edu.sa/ redirects to /en/ (English) or /ar/ (Arabic).
  - robots.txt allows all content pages; only CMS/admin/asset folders are
    disallowed.
  - The site has only five discoverable content pages relevant to training:
      /en/training-programs   — lists three broad diploma programmes
      /en/safety-health-environment — SHE policy page, no course info
      /en/students-registration     — 403 Forbidden
      /en/news-events               — press releases, no schedule tables
      /en/nma-faqs                  — no course dates
  - Short-course / STCW paths (/en/stcw, /en/short-courses, /en/schedule,
    /en/calendar) all return 404.
  - The registration portal at https://nationalmaritime.academy/ is a
    separate domain with an intake form only; no public course calendar.
  - No tables, no date data, no STCW course IDs (PST, FPFF, EFA, PSSR,
    PSCRB, AFF, MFA, MC, FRB) appear anywhere on the public site.

Verdict: NOT SCRAPEABLE with current site structure.  The adapter fetches
the training-programs page and confirms it is still content-free before
returning [].  If NMA publishes a course calendar in future this adapter
is the correct place to implement parsing.
"""
import logging
import time

import requests
from bs4 import BeautifulSoup

from pipeline.adapters.base import BaseAdapter, Offering
from pipeline.normalise import safe_url  # noqa: F401 — kept for future use

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; "
    "+https://github.com/bcheevers123/id-rather-be-sailing)"
)

BASE_URL = "https://www.nma.edu.sa/en"

# Known content pages that might one day carry schedule data
_CANDIDATE_URLS = [
    f"{BASE_URL}/training-programs",
    f"{BASE_URL}/short-courses",
    f"{BASE_URL}/schedule",
    f"{BASE_URL}/calendar",
    f"{BASE_URL}/stcw",
]

# STCW course keywords → normalised course IDs (ready for when dates appear)
_COURSE_ID_MAP = [
    ("personal survival techniques", "pst"),
    ("fire prevention", "fpff"),
    ("elementary first aid", "efa"),
    ("personal safety", "pssr"),
    ("proficiency in survival craft", "pscrb"),
    ("advanced fire fighting", "aff"),
    ("medical first aid", "mfa"),
    ("medical care", "mc"),
    ("fast rescue", "frb"),
    (" pst ", "pst"),
    (" fpff ", "fpff"),
    (" efa ", "efa"),
    (" pssr ", "pssr"),
    (" pscrb ", "pscrb"),
    (" aff ", "aff"),
    (" mfa ", "mfa"),
    (" mc ", "mc"),
    (" frb ", "frb"),
]


def _contains_course_dates(html: str) -> bool:
    """Return True if the page contains any date-like table data."""
    soup = BeautifulSoup(html, "lxml")
    # Look for <table> elements with date-shaped cells
    for table in soup.find_all("table"):
        text = table.get_text()
        # Rough heuristics: four-digit year adjacent to a month-ish number
        import re
        if re.search(r"\b(20\d\d)\b", text):
            return True
    return False


class NmaSaAdapter(BaseAdapter):
    """Adapter for the National Maritime Academy, Saudi Arabia.

    Returns an empty list until NMA publishes a public STCW course calendar.
    The fetch() method still makes a live HEAD/GET to the training-programs
    page so that future monitoring can detect when content appears.
    """

    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        for url in _CANDIDATE_URLS:
            try:
                resp = session.get(url, timeout=20, allow_redirects=True)
            except Exception as e:
                logger.warning("NMA SA: request failed for %s: %s", url, e)
                time.sleep(2)
                continue
            time.sleep(2)

            if resp.status_code == 404:
                logger.debug("NMA SA: 404 for %s (expected)", url)
                continue
            if resp.status_code != 200:
                logger.warning(
                    "NMA SA: unexpected HTTP %s for %s", resp.status_code, url
                )
                continue

            try:
                if _contains_course_dates(resp.text):
                    logger.info(
                        "NMA SA: date-like content detected at %s — "
                        "manual parsing implementation needed",
                        url,
                    )
            except Exception as e:
                logger.warning("NMA SA: parse error for %s: %s", url, e)

        logger.info(
            "NMA SA: no scrapeable STCW course schedule found on %s — "
            "returning []",
            provider.get("website", BASE_URL),
        )
        return []
