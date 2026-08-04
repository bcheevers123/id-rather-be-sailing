"""Ocean Technologies Group (OceanTG) adapter.

Scouted: https://oceantg.com

Result: not scrapeable for scheduled STCW course dates.

Findings
--------
1. ``oceantg.com`` issues an HTTP 301 to ``oneocean.com`` (owned by
   Lloyd's Register) for every path.  The domain itself carries no
   schedule data.

2. The associated e-commerce shop at ``shop.oceantg.com`` offers
   online self-paced courses (Maritime Marlins, Seagull and Videotel
   titles).  None of the STCW course listings carry specific start or
   end dates — they are self-paced online purchases only.

3. ``oneocean.com`` has ``Disallow: /api/`` in its robots.txt; its
   backend API is explicitly off-limits.

4. No instructor-led classroom sessions with scheduled dates were found
   on any reachable page under either domain.

robots.txt (oneocean.com, the redirect target):
    Disallow: /?s=
    Disallow: /wp-admin/
    Allow:    /wp-admin/admin-ajax.php
    Disallow: /api/

Because no scrapeable schedule data exists, this adapter always returns
an empty list.  If OceanTG / One Ocean publish a structured schedule in
future (e.g. a JSON feed or an HTML table at a stable URL), re-examine
the domain and implement parsing here.

Provider IDs: ``ocean-tg-uk-ltd-previously-marlins-and-videotel``,
              ``ocean-tg-uk-ltd-previously-marlins-and-videotel-2``.
"""
from __future__ import annotations

import logging

from pipeline.adapters.base import BaseAdapter, Offering

logger = logging.getLogger(__name__)


class OceanTgAdapter(BaseAdapter):
    """OceanTG / One Ocean adapter — returns no offerings.

    oceantg.com redirects entirely to oneocean.com.  The only customer-
    facing course shop (shop.oceantg.com) sells self-paced e-learning
    with no scheduled dates, so there is nothing to scrape.
    """

    def fetch(self, provider: dict) -> list[Offering]:
        """Return an empty list — no scheduled offerings are published.

        No network requests are made; the domain has no scrapeable
        schedule pages.
        """
        logger.info(
            "OceanTG adapter: oceantg.com redirects to oneocean.com and "
            "offers only self-paced e-learning; returning 0 offerings for %s.",
            provider.get("id"),
        )
        return []
