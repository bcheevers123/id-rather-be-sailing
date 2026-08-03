import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

from pipeline.normalise import make_slug, extract_contact_parts

logger = logging.getLogger(__name__)

_NOT_PUBLIC_RE = re.compile(r"not open to public", re.I)
_OUTSIDE_UK_HEADING_RE = re.compile(r"outside.*uk|non.uk", re.I)


@dataclass
class RawProvider:
    raw_name: str
    location: str
    address: str
    contact_details: str
    not_open_to_public: bool
    is_uk: bool = True


@dataclass
class RawApproval:
    course_id: str
    raw_provider_name: str
    source_pdf_url: str
    source_updated_date: str
    not_open_to_public: bool


@dataclass
class ParsedPdf:
    providers: list[RawProvider] = field(default_factory=list)
    approvals: list[RawApproval] = field(default_factory=list)


def _clean(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(text.split())


def parse_pdf(pdf_path: Path, course_id: str, pdf_url: str, source_updated_date: str) -> ParsedPdf:
    result = ParsedPdf()
    is_uk_section = True

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""

            # Detect switch to "outside UK" section
            if _OUTSIDE_UK_HEADING_RE.search(text):
                is_uk_section = False

            # Use table extraction first; fall back to text parsing
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    for row in table:
                        if not row or len(row) < 2:
                            continue
                        name_cell = _clean(row[0]) if row[0] else ""
                        location_cell = _clean(row[1]) if len(row) > 1 and row[1] else ""
                        address_cell = _clean(row[2]) if len(row) > 2 and row[2] else ""
                        contact_cell = _clean(row[3]) if len(row) > 3 and row[3] else ""

                        # Skip header rows
                        if not name_cell or name_cell.lower() in ("training provider", "provider"):
                            continue

                        not_public = _NOT_PUBLIC_RE.search(address_cell + contact_cell) is not None

                        provider = RawProvider(
                            raw_name=name_cell,
                            location=location_cell,
                            address=address_cell,
                            contact_details=contact_cell,
                            not_open_to_public=not_public,
                            is_uk=is_uk_section,
                        )
                        result.providers.append(provider)
                        result.approvals.append(RawApproval(
                            course_id=course_id,
                            raw_provider_name=name_cell,
                            source_pdf_url=pdf_url,
                            source_updated_date=source_updated_date,
                            not_open_to_public=not_public,
                        ))
            else:
                logger.warning("No tables found on page %s of %s — using text fallback", page.page_number, pdf_path.name)

    logger.info("Parsed %d providers from %s", len(result.providers), pdf_path.name)
    return result
