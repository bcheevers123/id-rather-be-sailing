"""South Tyneside College (Radio) adapter.

Scouting summary (2026-08-04)
------------------------------
The provider record "tyne-coast-college-radio" / "tyne-coast-college-radio-2"
points to https://www.stc.ac.uk/ and represents the Marine and Offshore Safety
Training department at Wapping Street, South Shields (email: marine@stc.ac.uk).

robots.txt: open (Disallow: [empty] — no restrictions).

On-site investigation:
- stc.ac.uk/courses/ lists ~30 vocational subjects; no maritime or radio
  courses appear anywhere in the A-Z listing.
- stc.ac.uk/marine  →  301 redirect to https://www.southshieldsmarineschool.com/
- stc.ac.uk/marine/ →  301 redirect to https://www.southshieldsmarineschool.com//
- stc.ac.uk/event-sitemap.xml lists only "advice-enrolment-event" pages
  (open-day events, not course schedules).
- Searching for "radio", "GMDSS", "SRC", "LRC", "VHF", "maritime" on the
  stc.ac.uk domain returns no results.

The marine/radio training that these provider records refer to is delivered
under the South Tyneside Marine School brand and served from
southshieldsmarineschool.com — a completely separate domain that is already
covered by the south_shields.py adapter (EBSonTrack booking system).

Because stc.ac.uk itself publishes no STCW or radio course schedule data,
this adapter returns [] to avoid duplicating the South Shields Marine School
data that south_shields.py already collects.

Re-scout trigger: if stc.ac.uk introduces a dedicated maritime/radio course
listing at a URL such as stc.ac.uk/radio/ or stc.ac.uk/maritime/, this
adapter should be updated to scrape those pages.
"""

import logging

from pipeline.adapters.base import BaseAdapter, Offering

logger = logging.getLogger(__name__)


class StcAdapter(BaseAdapter):
    """Stub adapter for South Tyneside College (Radio).

    stc.ac.uk publishes no STCW or radio course schedule pages;
    marine/radio training redirects to southshieldsmarineschool.com
    which is covered by the south_shields.py adapter.
    Returns an empty list until the site publishes scrapeable schedule data.
    """

    def fetch(self, provider: dict) -> list[Offering]:
        logger.info(
            "StcAdapter: no scrapeable schedule at stc.ac.uk — returning [] "
            "(marine pages redirect to southshieldsmarineschool.com; "
            "see south_shields.py for that data)"
        )
        return []
