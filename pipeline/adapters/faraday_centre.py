"""The Faraday Centre adapter for faradaycentre.co.uk.

Site overview
-------------
The Faraday Centre is a specialist electrical-safety training provider based
in Redcar, Cleveland.  Its course catalogue covers battery, low-voltage,
high-voltage, marine/offshore high-voltage, mechanical, protection, and
testing subjects.

robots.txt
----------
faradaycentre.co.uk/robots.txt is present and contains:

    User-agent: *
    Disallow:

No restrictions apply — the wildcard agent is allowed everywhere.

Radio / GMDSS coverage
-----------------------
The Faraday Centre does NOT offer any of the radio or GMDSS courses tracked
by this project (GOC, ROC, LRC, or similar).  Site searches for "GMDSS" and
"radio" both return "No items found".  The Marine/Offshore section covers only
high-voltage power-system safety (MAR1-MAR7, MCA4).

For this reason the adapter returns an empty list without making any HTTP
requests.  If The Faraday Centre adds radio courses in future, this stub
should be replaced with a real scraper.
"""

import logging

from pipeline.adapters.base import BaseAdapter, Offering

logger = logging.getLogger(__name__)


class FaradayCentreAdapter(BaseAdapter):
    """Adapter for The Faraday Centre (faradaycentre.co.uk).

    The Faraday Centre offers only electrical-safety training and does not
    run any of the radio/GMDSS courses tracked by this project (GOC, ROC,
    LRC, Security Awareness, etc.).  The adapter always returns an empty
    list.
    """

    def fetch(self, provider: dict) -> list[Offering]:
        """Return [] — Faraday Centre offers no radio/GMDSS courses."""
        logger.debug(
            "FaradayCentreAdapter: provider %s offers no radio/GMDSS courses; "
            "returning empty list.",
            provider.get("id"),
        )
        return []
