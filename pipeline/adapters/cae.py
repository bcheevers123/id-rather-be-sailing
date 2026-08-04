"""CAE Training and Services UK LTD adapter.

No public STCW / maritime seafarer course schedule is accessible on cae.com.

Investigation summary (fetched 2026-08-04):
  - cae.com has no robots.txt (HTTP 404), so no crawling restrictions apply.
  - cae.com/sitemap.xml contains only aviation, defence, and press-release
    URLs; no maritime-training entries are present.
  - cae.com/defense-security/maritime describes military naval simulation
    systems (training devices, training centres), not open-enrolment STCW
    programmes for seafarers.
  - Multiple candidate URL patterns (/maritime/, /maritime-training,
    /civil-aviation/training-solutions/maritime/, /training-services/, etc.)
    all return HTTP 404.

"CAE Training and Services UK LTD" (the MCA-listed entity) may operate via
a separate booking portal or direct-sales channel that is not publicly
browsable.  Re-evaluate if CAE publishes a dedicated STCW course-schedule
page under their domain.

This adapter returns [] until a scrapeable public schedule page is found.
"""
import logging

from pipeline.adapters.base import BaseAdapter, Offering

logger = logging.getLogger(__name__)


class CaeAdapter(BaseAdapter):
    """Stub adapter for CAE Training and Services UK LTD.

    Returns an empty list because cae.com does not expose a public STCW
    course schedule.  See module docstring for full investigation notes.
    """

    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:  # noqa: ARG002
        logger.info(
            "CaeAdapter: no public schedule page found for cae.com — returning []"
        )
        return []
