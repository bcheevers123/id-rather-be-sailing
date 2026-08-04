"""H. Lavity Stoutt Community College (HLSCC) adapter.

HLSCC operates the Centre for Applied Marine Studies (CAMS) on Tortola,
British Virgin Islands, and offers STCW Basic Safety Training, VHF Marine
Radio (ROC/GOC), and RYA short courses.

Why this adapter returns []:
-----------------------------
1. The primary domain ``hlscc.org`` now serves only a redirect page pointing
   to ``hlscc.edu.vg``.

2. ``hlscc.edu.vg`` (robots.txt: ``Allow: /``, ``Disallow: /*?*``) has no
   machine-readable course schedule.  All STCW/maritime course pages describe
   programmes in general terms but publish no dates, prices, or booking links.

3. The dedicated marine-training subdomain ``cams.hlscc.edu.vg`` returns an
   TLS internal error (``TLSV1_ALERT_INTERNAL_ERROR``) for every request,
   making it unreachable at the time of writing (verified 2026-08-04).

4. The site uses The Events Calendar (WordPress plugin) but the REST endpoint
   ``/wp-json/tribe/events/v1/events`` returns ``"events": [], "total": 0``
   for the next two years; the ``/upcoming-events/`` page similarly states
   "There are no upcoming events."

5. The application portal (``apply.hlscc.edu.vg``) requires authentication.

Action required:
    If HLSCC makes a public schedule available — either via their events
    calendar, on ``cams.hlscc.edu.vg``, or on a new page — this stub should
    be replaced with a real implementation.  Contact: marine@hlscc.edu.vg.

Source URLs investigated:
    https://hlscc.edu.vg/centre-for-applied-marine-studies/
    https://hlscc.edu.vg/marine-professional-training/
    https://hlscc.edu.vg/upcoming-events/
    https://hlscc.edu.vg/wp-json/tribe/events/v1/events
    https://cams.hlscc.edu.vg/   (SSL error)
"""

import logging

from pipeline.adapters.base import BaseAdapter, Offering

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; "
    "+https://github.com/bcheevers123/id-rather-be-sailing)"
)

# Canonical source URL — the CAMS programme page that would contain schedule
# data if the site ever publishes it publicly.
SOURCE_URL = "https://hlscc.edu.vg/centre-for-applied-marine-studies/"


class HlsccAdapter(BaseAdapter):
    """Adapter for H. Lavity Stoutt Community College (HLSCC), British Virgin Islands.

    Returns an empty list because HLSCC does not currently publish a public
    STCW course schedule.  See module docstring for full investigation notes.
    """

    def fetch(self, provider: dict) -> list[Offering]:
        """Return [] — no public schedule is available on hlscc.edu.vg.

        The college offers STCW Basic Safety Training, VHF Marine Radio
        (ROC/GOC), and RYA courses via its Centre for Applied Marine Studies,
        but publishes no dates, prices, or booking links on any publicly
        accessible, machine-readable page.

        Args:
            provider: Provider dict from providers.json (id, website, …).

        Returns:
            Empty list.
        """
        logger.info(
            "HLSCC adapter: no public schedule available for provider %s — returning []",
            provider.get("id"),
        )
        return []
