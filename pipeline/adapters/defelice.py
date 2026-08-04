"""Agenzia Marittima De Felice Srl adapter (Viareggio, Italy).

De Felice is a full-service maritime agency based in Viareggio, LU, Italy that
also organises STCW Manila 2010 training courses leading to MCA-issued
competency certificates. Certifying bodies include DNV, MCA, Marlins, and PYA.

Site: https://www.defelice.yachts
Training: https://www.defelice.yachts/en/training
Calendar: https://www.defelice.yachts/en/list-courses?type=calendar

robots.txt (scouted 2026-08-04): ``User-agent: *`` / ``Disallow:`` (empty) —
all crawlers are permitted with no path restrictions.

Scouting findings (2026-08-04)
--------------------------------
The public course calendar page at ``/en/list-courses?type=calendar`` displays
the message:

    "Sorry, the course calendar is still under construction."
    (IT: "Il calendario dei corsi è ancora in costruzione.")

No course dates, prices, booking links, or machine-readable schedule data are
exposed on any public page.  The training section lists five broad course
families (Deck, Engineering, Leadership & Management, Safety and Security,
Yacht Etiquette) but contains only descriptive text with no schedulable
offerings.  Interested parties are directed to contact the office directly:

    Via M. Coppino 433, 55049 Viareggio (LU)
    +39 0584 38 48 84

Action required
---------------
This adapter should be re-scouted whenever the calendar page becomes live.
The URL to check is ``https://www.defelice.yachts/en/list-courses?type=calendar``.
When the calendar is populated, implement date/course parsing against the new
page structure and remove the early-return stub below.
"""
import logging
from datetime import datetime, timezone

from pipeline.adapters.base import BaseAdapter, Offering

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0;"
    " +https://github.com/bcheevers123/id-rather-be-sailing)"
)

_CALENDAR_URL = "https://www.defelice.yachts/en/list-courses?type=calendar"
_TRAINING_URL = "https://www.defelice.yachts/en/training"


class DefeliceAdapter(BaseAdapter):
    """Adapter for Agenzia Marittima De Felice Srl, Viareggio, Italy.

    Returns an empty list because the public course calendar is explicitly
    marked as "still under construction" on the live site (verified 2026-08-04).
    No dates, prices, or booking links are available for scraping.

    Re-scout trigger: check ``_CALENDAR_URL`` for populated course rows.
    """

    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        """Return course offerings for De Felice.

        Currently returns [] — the site's calendar page is under construction
        and exposes no public schedule data.  See module docstring for details.
        """
        now = datetime.now(timezone.utc).isoformat()
        logger.info(
            "DefeliceAdapter: calendar under construction at %s — "
            "returning 0 offerings for provider_id=%s (last_verified=%s)",
            _CALENDAR_URL,
            provider.get("id"),
            now,
        )
        return []
