"""MedAire superyacht medical training adapter.

MedAire (medaire.com) is an MCA-certified provider offering STCW'10 medical
training for superyacht crew.  Training is delivered onboard the client's
vessel by MedAire instructors — there is no fixed public schedule or
location-based course calendar.

robots.txt check (Aug 2026):
  No Disallow: / for general user agents.
  Only HubSpot preview/preference paths are disallowed.
  General crawling is permitted.

STCW courses confirmed on the site (https://www.medaire.com/yachts/medical-training):
  - Elementary First Aid (EFA)                 → course_id: efa
  - Proficiency in Medical First Aid (PMFA)    → course_id: mfa
  - Proficiency in Medical Care Onboard (PMCOB)→ course_id: mc

Why this adapter returns []:
  Courses are delivered on-demand aboard the client's vessel.  MedAire does
  not publish scheduled open-enrolment dates, prices, or a booking calendar
  on any publicly crawlable page.  The booking flow uses training vouchers
  sold through their U.S. eShop (app.medaire.com), which requires an account.

  To enable real offerings, MedAire would need to either:
    - Publish an open-enrolment schedule page, or
    - Expose a public course calendar (e.g. via an API or booking widget).

Provider ID : medaire-limited  (and -2 / -3 variants)
Website     : https://www.medaire.com
Training    : https://www.medaire.com/yachts/medical-training
Contact     : via https://www.medaire.com/contact
"""
import logging
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from pipeline.adapters.base import BaseAdapter, Offering

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; "
    "+https://github.com/bcheevers123/id-rather-be-sailing)"
)

TRAINING_URL = "https://www.medaire.com/yachts/medical-training"

# STCW course IDs confirmed as offered by MedAire (no schedule published).
_CONFIRMED_COURSES = ["efa", "mfa", "mc"]


class MedAireAdapter(BaseAdapter):
    """Adapter for MedAire superyacht medical training.

    NOTE: MedAire delivers STCW medical courses exclusively onboard client
    vessels and does not publish open-enrolment dates or pricing online.
    This adapter confirms the site is reachable and documents which STCW
    courses are offered, but always returns an empty list because no
    schedulable data is available to harvest.
    """

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "en-GB,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )

        # Verify the training page is still live.
        try:
            resp = session.get(TRAINING_URL, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("MedAire: fetch failed for %s: %s", TRAINING_URL, exc)
            return []
        time.sleep(2)

        # Spot-check that the page still references STCW content.
        try:
            soup = BeautifulSoup(resp.text, "lxml")
            page_text = soup.get_text(" ", strip=True).lower()
            stcw_present = "stcw" in page_text or "elementary first aid" in page_text
        except Exception as exc:
            logger.warning("MedAire: parse failed for %s: %s", TRAINING_URL, exc)
            stcw_present = False

        logger.info(
            "MedAire: site live=%s, STCW content detected=%s, "
            "confirmed courses=%s. "
            "No public schedule — returning 0 offerings.",
            True,
            stcw_present,
            _CONFIRMED_COURSES,
        )

        # Training is delivered on-demand aboard client vessels.
        # No public schedule exists to scrape.
        return []
