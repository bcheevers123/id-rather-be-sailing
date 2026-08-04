"""Evergreen Seafarer Training Center adapter — evergreen-marine.com.

Domain investigation summary
-----------------------------
Domain : www.evergreen-marine.com
robots.txt : Allows the IdRatherBeSailing crawler. The file blocks 107
    specific named AI and indexing bots by individual User-agent entries
    (each paired with ``Disallow: /``), but there is **no** blanket
    ``User-agent: *`` block.  Our custom User-Agent is not listed, so
    crawling is permitted.

The domain www.evergreen-marine.com belongs to **Evergreen Marine Corp.**,
a container shipping company headquartered in Taiwan.  The public website
covers cargo booking, vessel tracking, investor relations, and corporate
governance — there are no STCW course schedule pages, no training calendar,
and no booking interface for seafarer courses.

The training entity, "Evergreen Seafarer Training Center" (Kaohsiung,
Taiwan; and a Philippines facility), is associated with Evergreen Marine
Corp. but does not expose a publicly accessible online course schedule
through this domain.  Attempted subdomains (training.*, estc.*) do not
resolve in DNS.  A PDF-based training schedule may exist but is not
discoverable without authentication or a direct link.

Robots.txt conclusion
---------------------
No ``User-agent: *  Disallow: /`` rule — crawling is *not* blocked for our
User-Agent.  However, no schedule data is accessible, so the adapter
returns an empty list regardless.

Provider IDs served: ``evergreen-seafarer-training-center-4``,
                     ``evergreen-seafarer-training-center-5``.
"""
from __future__ import annotations

import logging

from pipeline.adapters.base import BaseAdapter, Offering

logger = logging.getLogger(__name__)


class EvergreenMarineAdapter(BaseAdapter):
    """Evergreen Seafarer Training Center adapter — returns no offerings.

    www.evergreen-marine.com is the website of Evergreen Marine Corp.
    (a container shipping line).  The associated seafarer training centre
    does not publish a public STCW course schedule through this domain.

    No subdomains carrying a training schedule are publicly reachable, so
    no network requests are made and an empty list is returned.

    If a public schedule URL is identified in future (e.g. a PDF calendar
    or an HTML timetable page), implement the HTTP fetch and HTML parsing
    here and re-verify against robots.txt before deployment.
    """

    def fetch(self, provider: dict) -> list[Offering]:
        """Return an empty list — no public schedule is available.

        The Evergreen Seafarer Training Center does not publish scheduled
        STCW course dates on www.evergreen-marine.com or any resolvable
        subdomain.  Returning 0 offerings without making any network
        requests.
        """
        logger.info(
            "EvergreenMarine adapter: no public STCW schedule found on "
            "evergreen-marine.com; returning 0 offerings for %s.",
            provider.get("id"),
        )
        return []
