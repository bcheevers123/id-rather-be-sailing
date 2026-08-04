"""Securewest International adapter — securewest.com.

Domain investigation summary
-----------------------------
Domain : www.securewest.com
robots.txt : ``User-agent: *`` block with only two Disallow rules —
    ``/wp-admin/`` and ``/assets/``.  All public-facing pages are
    explicitly allowed.  The sitemap is referenced at
    https://www.securewest.com/sitemap_index.xml.

Securewest International is a UK-based maritime security company
(MCA-approved training provider, Plymouth, Devon).  Their online training
hub at https://www.securewest.com/online-training/ lists three courses:

1. Proficiency in STCW Security Awareness (PSA / security-awareness)
   URL    : https://www.securewest.com/product/proficiency-in-security-awareness-psa/
   Price  : £50.00 GBP
   Format : Fully online, self-paced — immediate access on purchase.
   Duration: 3–4 hours.

2. Proficiency in Designated Security Duties (DSD / dsd)
   URL    : https://www.securewest.com/product/proficiency-for-seafarers-with-designated-security-duties/
   Price  : £145.00 GBP
   Format : Fully online, self-paced — immediate access on purchase.
   Duration: 8–10 hours.

3. Travel Safety & Awareness (not an STCW course — outside project scope)

Neither STCW course carries a specific start date or cohort schedule.
Both are on-demand purchases: learners enrol and start immediately, at
their own pace.  There is no concept of a "course run" with a start_date
and end_date, so no Offering records can be emitted.

No SSO (Ship Security Officer) instructor-led or blended courses with a
published calendar were found on any reachable page.

robots.txt conclusion
---------------------
No blanket disallow — crawling the training pages is permitted.  However,
because the offerings are self-paced with no schedule, the adapter returns
an empty list.

Provider IDs served: ``securewest-international``,
                     ``securewest-international-2``.
"""
from __future__ import annotations

import logging

from pipeline.adapters.base import BaseAdapter, Offering

logger = logging.getLogger(__name__)


class SecurewestAdapter(BaseAdapter):
    """Securewest International adapter — returns no offerings.

    All STCW courses on securewest.com (PSA £50, DSD £145) are fully
    online and self-paced with no scheduled start or end dates.  Because
    no course calendar or timetable is published, there is nothing to
    scrape and no Offering records can be produced.

    If Securewest introduces instructor-led or blended courses with a
    published schedule, add HTTP fetching and parsing logic here.
    Verify robots.txt compliance before deploying any such change.
    """

    def fetch(self, provider: dict) -> list[Offering]:
        """Return an empty list — all courses are self-paced with no dates.

        securewest.com publishes only on-demand e-learning courses
        (PSA, DSD).  Neither carries a specific start date, so no
        Offering records can be emitted.  No network requests are made.
        """
        logger.info(
            "Securewest adapter: all courses on securewest.com are self-paced "
            "e-learning with no scheduled dates; returning 0 offerings for %s.",
            provider.get("id"),
        )
        return []
