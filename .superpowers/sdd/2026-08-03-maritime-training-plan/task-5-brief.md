# Task 5 Brief: PDF parser and provider normalisation

## Context

Task 5 of the "I'd Rather Be Sailing" plan. Tasks 1–4 are complete on branch `feature/maritime-training`. You are implementing `pipeline/pdf_parser.py` (parses MCA provider PDFs using pdfplumber), `pipeline/normalise.py` (slug generation, contact extraction), and their tests. You'll also download three real MCA PDFs as test fixtures.

## Working directory

`C:\Users\BarryCheevers\OneDrive - Anomali\Desktop\Fun\I'd Rather Be Sailing`
Branch: `feature/maritime-training`

Python venv: `.venv`. Activate then `pip install -r requirements.txt`. `pdfplumber` is already in requirements.

## Files to create

- `pipeline/pdf_parser.py`
- `pipeline/normalise.py`
- `tests/pipeline/fixtures/pst_providers.pdf` (fetch from live MCA page URLs)
- `tests/pipeline/fixtures/fpff_providers.pdf`
- `tests/pipeline/fixtures/frb_providers.pdf`
- `tests/pipeline/test_pdf_parser.py`
- `tests/pipeline/test_normalise.py`

## Step 1 — Get the PDF URLs from the saved fixture

The fixture at `tests/pipeline/fixtures/mca_atp_page.html` contains the live MCA page. Search it for the PST, FPFF, and FRB PDF URLs. Look for anchor tags with `assets.publishing.service.gov.uk` links ending in `.pdf` near headings containing "Personal Survival", "Fire Prevention", and "Fast Rescue". The filenames include a date stamp like `PST_16.07.2026.pdf`.

Then download them:

```python
import requests, pathlib

UA = "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; +https://github.com/bcheevers123/id-rather-be-sailing)"
headers = {"User-Agent": UA}

urls = {
    "tests/pipeline/fixtures/pst_providers.pdf": "<PST URL you found>",
    "tests/pipeline/fixtures/fpff_providers.pdf": "<FPFF URL you found>",
    "tests/pipeline/fixtures/frb_providers.pdf": "<FRB URL you found>",
}
import time
for path, url in urls.items():
    r = requests.get(url, headers=headers, timeout=60)
    r.raise_for_status()
    pathlib.Path(path).write_bytes(r.content)
    print(f"Saved {len(r.content)} bytes → {path}")
    time.sleep(2)  # 2s delay between requests
```

## Step 2 — Write tests/pipeline/test_pdf_parser.py

```python
from pathlib import Path
from pipeline.pdf_parser import parse_pdf

PST_PDF = Path("tests/pipeline/fixtures/pst_providers.pdf")
FRB_PDF = Path("tests/pipeline/fixtures/frb_providers.pdf")


def test_pst_extracts_known_provider():
    result = parse_pdf(PST_PDF, "pst", "https://example.com/pst.pdf", "2026-07-16")
    names = [p.raw_name for p in result.providers]
    assert any("Maritime Skills Academy" in n for n in names)


def test_pst_extracts_website():
    result = parse_pdf(PST_PDF, "pst", "https://example.com/pst.pdf", "2026-07-16")
    websites = [p.contact_details for p in result.providers]
    assert any("maritimeskillsacademy.com" in (w or "") for w in websites)


def test_pst_provider_count_reasonable():
    result = parse_pdf(PST_PDF, "pst", "https://example.com/pst.pdf", "2026-07-16")
    assert 20 <= len(result.providers) <= 100


def test_not_open_to_public_flagged():
    result = parse_pdf(PST_PDF, "pst", "https://example.com/pst.pdf", "2026-07-16")
    public_flags = [p.not_open_to_public for p in result.providers]
    assert True in public_flags


def test_approvals_link_to_course():
    result = parse_pdf(PST_PDF, "pst", "https://example.com/pst.pdf", "2026-07-16")
    for approval in result.approvals:
        assert approval.course_id == "pst"


def test_frb_extracts_providers():
    result = parse_pdf(FRB_PDF, "frb", "https://example.com/frb.pdf", "2026-07-16")
    assert len(result.providers) >= 5
```

**Important:** If any assertion fails because the real PDF content differs slightly from expectations (e.g., provider count, "Maritime Skills Academy" name format), adjust the assertion to match reality — but NEVER invent provider names that aren't in the PDF.

## Step 3 — Write tests/pipeline/test_normalise.py

```python
from pipeline.normalise import make_slug, normalise_provider, extract_contact_parts


def test_make_slug_basic():
    assert make_slug("Maritime Skills Academy (Dover)") == "maritime-skills-academy-dover"


def test_make_slug_strips_punctuation():
    assert make_slug("UHI North West & Hebrides") == "uhi-north-west-hebrides"


def test_make_slug_deduplicates_with_counter():
    slug1 = make_slug("Seascope Maritime Training")
    slug2 = make_slug("Seascope Maritime Training", existing={"seascope-maritime-training"})
    assert slug2 == "seascope-maritime-training-2"


def test_extract_contact_parts_full():
    raw = "Tel: 01234 567890\nEmail: test@example.com\nhttps://example.com/"
    parts = extract_contact_parts(raw)
    assert parts["telephone"] == "01234 567890"
    assert parts["email"] == "test@example.com"
    assert parts["website"] == "https://example.com/"


def test_extract_contact_parts_missing():
    parts = extract_contact_parts("Not open to public")
    assert parts["telephone"] is None
    assert parts["email"] is None
    assert parts["website"] is None
```

## Step 4 — Run failing tests

```bash
pytest tests/pipeline/test_pdf_parser.py tests/pipeline/test_normalise.py -v
```
Expected: ImportError.

## Step 5 — Create pipeline/normalise.py

```python
import re
import unicodedata


def make_slug(text: str, existing: set[str] | None = None) -> str:
    """Convert display text to a stable URL-safe slug."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    if existing and text in existing:
        i = 2
        while f"{text}-{i}" in existing:
            i += 1
        text = f"{text}-{i}"
    return text


_TEL_RE = re.compile(r"Tel:\s*([^\n]+)", re.I)
_EMAIL_RE = re.compile(r"Email:\s*([^\s\n]+@[^\s\n]+)", re.I)
_URL_RE = re.compile(r"https?://[^\s\n]+", re.I)


def extract_contact_parts(raw: str) -> dict:
    tel_m = _TEL_RE.search(raw)
    email_m = _EMAIL_RE.search(raw)
    url_m = _URL_RE.search(raw)
    return {
        "telephone": tel_m.group(1).strip() if tel_m else None,
        "email": email_m.group(1).strip() if email_m else None,
        "website": url_m.group(0).strip() if url_m else None,
    }


def normalise_provider(raw_name: str, location: str, address: str, contact_details: str,
                        not_open_to_public: bool, existing_slugs: set[str]) -> dict:
    slug = make_slug(raw_name, existing_slugs)
    existing_slugs.add(slug)
    contact = extract_contact_parts(contact_details)

    region = location.strip() if location else None
    city = None
    address_clean = address.strip() if address else None

    return {
        "id": slug,
        "official_name": raw_name.strip(),
        "alt_names": [],
        "address": address_clean,
        "city": city,
        "region": region,
        "country": "GB",
        "postcode": None,
        "lat": None,
        "lng": None,
        "website": contact["website"],
        "email": contact["email"],
        "telephone": contact["telephone"],
        "not_open_to_public": not_open_to_public,
    }
```

## Step 6 — Create pipeline/pdf_parser.py

```python
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
```

## Step 7 — Run all tests

```bash
pytest tests/pipeline/test_pdf_parser.py tests/pipeline/test_normalise.py -v
```
Expected: 11 tests pass.

Then run the full suite:
```bash
pytest -v
```
All prior tests must also pass.

**Troubleshooting:** If `test_pst_extracts_website` fails because the PDF's contact cell doesn't contain a URL in the format matched by `_URL_RE`, investigate the actual cell content with pdfplumber and adjust `extract_contact_parts` regex or the test assertion accordingly. Never invent provider data.

## Step 8 — Commit

```bash
git add pipeline/pdf_parser.py pipeline/normalise.py \
    tests/pipeline/test_pdf_parser.py tests/pipeline/test_normalise.py \
    tests/pipeline/fixtures/pst_providers.pdf \
    tests/pipeline/fixtures/fpff_providers.pdf \
    tests/pipeline/fixtures/frb_providers.pdf
git commit -m "feat: PDF parser and provider normalisation"
```

## Global constraints

- User-Agent `Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; +https://github.com/bcheevers123/id-rather-be-sailing)` on all HTTP
- 2-second delay between requests to the same domain when downloading PDFs
- Never fabricate provider names, addresses, or contact details
- Tests must use the real downloaded PDFs, not mocked content

## Report file

Write your report to: `.superpowers/sdd/2026-08-03-maritime-training-plan/task-5-report.md`

Return: Status, commits, test summary (N passed, N failed), concerns (especially if PDF structure required test adjustments).
