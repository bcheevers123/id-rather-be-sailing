# Task 4 Brief: MCA source discovery

## Context

Task 4 of the "I'd Rather Be Sailing" plan. Scaffold (Task 1), docs (Task 2), and JSON schemas + validate module (Task 3) are all complete on branch `feature/maritime-training`. You are implementing `pipeline/mca_source.py` — the module that fetches the MCA ATP guidance page and discovers current PDF URLs dynamically.

## Working directory

`C:\Users\BarryCheevers\OneDrive - Anomali\Desktop\Fun\I'd Rather Be Sailing`
Branch: `feature/maritime-training`

Python venv: `.venv` (create with `python -m venv .venv` if needed, then `pip install -r requirements.txt`).

## Files to create

- `pipeline/mca_source.py`
- `tests/pipeline/fixtures/mca_atp_page.html` (fetched from live MCA page — save as HTML fixture)
- `tests/pipeline/test_mca_source.py`

## Interfaces produced (used by Task 8 — pipeline orchestrator)

```python
from dataclasses import dataclass

@dataclass
class PdfLink:
    course_name: str
    url: str
    category: str

def download_mca_page(session: requests.Session) -> str:
    """Fetch the MCA ATP guidance page, return HTML string."""

def fetch_pdf_links(html: str) -> list[PdfLink]:
    """Parse HTML, return list of PDF links with course name and category."""
```

## Implementation

### Step 1 — Save the HTML fixture (run once)

```python
import requests
r = requests.get(
    'https://www.gov.uk/guidance/mca-approved-training-providers-atp',
    headers={'User-Agent': 'Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; +https://github.com/bcheevers123/id-rather-be-sailing)'}
)
open('tests/pipeline/fixtures/mca_atp_page.html', 'w', encoding='utf-8').write(r.text)
print('Saved', len(r.text), 'bytes')
```

Run this from the repo root. The fixture must be committed.

### Step 2 — Write tests/pipeline/test_mca_source.py

```python
from pathlib import Path
from pipeline.mca_source import fetch_pdf_links, PdfLink

FIXTURE = Path("tests/pipeline/fixtures/mca_atp_page.html").read_text(encoding="utf-8")


def test_discovers_pst_pdf():
    links = fetch_pdf_links(FIXTURE)
    names = [l.course_name for l in links]
    assert any("Personal Survival Techniques" in n for n in names)


def test_discovers_fpff_pdf():
    links = fetch_pdf_links(FIXTURE)
    names = [l.course_name for l in links]
    assert any("Fire Prevention" in n for n in names)


def test_all_links_are_pdf_urls():
    links = fetch_pdf_links(FIXTURE)
    for link in links:
        assert link.url.endswith(".pdf"), f"Non-PDF URL: {link.url}"
        assert "assets.publishing.service.gov.uk" in link.url


def test_link_count_reasonable():
    links = fetch_pdf_links(FIXTURE)
    # We know there are ~75 PDFs; allow a range
    assert 60 <= len(links) <= 120, f"Unexpected link count: {len(links)}"


def test_categories_assigned():
    links = fetch_pdf_links(FIXTURE)
    categories = {l.category for l in links}
    assert "stcw_basic" in categories
    assert "security" in categories
```

Note: the plan had a typo in `test_discovers_fpff_pdf` (`for l in names` should be `for l in links`) — the corrected version above is correct.

### Step 3 — Run tests to confirm ImportError/NameError (red phase)

```bash
pytest tests/pipeline/test_mca_source.py -v
```

### Step 4 — Create pipeline/mca_source.py

```python
import re
import logging
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; +https://github.com/bcheevers123/id-rather-be-sailing)"

MCA_ATP_URL = "https://www.gov.uk/guidance/mca-approved-training-providers-atp"

# Map section heading keywords → category IDs
_HEADING_CATEGORY_MAP = [
    (re.compile(r"basic training", re.I), "stcw_basic"),
    (re.compile(r"advanced training", re.I), "stcw_advanced"),
    (re.compile(r"updating stcw|refresher", re.I), "stcw_refresher"),
    (re.compile(r"tanker", re.I), "stcw_tanker"),
    (re.compile(r"IGF", re.I), "stcw_igf"),
    (re.compile(r"HELM", re.I), "stcw_helm"),
    (re.compile(r"ECDIS|NAEST", re.I), "stcw_ecdis_naest"),
    (re.compile(r"GMDSS|radio|operators certificate", re.I), "gmdss"),
    (re.compile(r"high voltage", re.I), "high_voltage"),
    (re.compile(r"security", re.I), "security"),
    (re.compile(r"deck yacht|yacht.*module", re.I), "deck_yacht"),
    (re.compile(r"small vessel engineer|SV\b", re.I), "sv_engineering"),
    (re.compile(r"engine course|AEC|AEPC|general engineering", re.I), "engineering_other"),
    (re.compile(r"polar", re.I), "polar"),
    (re.compile(r"workboat", re.I), "workboat"),
]


@dataclass
class PdfLink:
    course_name: str
    url: str
    category: str


def download_mca_page(session: requests.Session) -> str:
    resp = session.get(MCA_ATP_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    return resp.text


def _infer_category(heading_text: str) -> str:
    for pattern, category in _HEADING_CATEGORY_MAP:
        if pattern.search(heading_text):
            return category
    return "other"


def fetch_pdf_links(html: str) -> list[PdfLink]:
    soup = BeautifulSoup(html, "lxml")
    links: list[PdfLink] = []
    current_category = "other"
    current_heading = ""

    for element in soup.find_all(["h2", "h3", "a"]):
        if element.name in ("h2", "h3"):
            current_heading = element.get_text(strip=True)
            current_category = _infer_category(current_heading)
        elif element.name == "a":
            href = element.get("href", "")
            if "assets.publishing.service.gov.uk" in href and href.endswith(".pdf"):
                course_name = element.get_text(strip=True)
                if not course_name:
                    course_name = current_heading
                links.append(PdfLink(
                    course_name=course_name,
                    url=href,
                    category=current_category,
                ))

    logger.info("Discovered %d PDF links from MCA ATP page", len(links))
    return links
```

### Step 5 — Run tests (green phase)

```bash
pytest tests/pipeline/test_mca_source.py -v
```
Expected: 5 tests pass.

If a test fails because the live fixture doesn't match expectations (e.g., link count out of range, PST not found by that exact name), investigate the actual HTML and adjust the implementation or test assertions accordingly — but do NOT fabricate course names or invent URLs. The fixture is real data.

### Step 6 — Run full test suite

```bash
pytest -v
```
All prior tests (test_validate.py) must still pass.

### Step 7 — Commit

```bash
git add pipeline/mca_source.py tests/pipeline/test_mca_source.py tests/pipeline/fixtures/mca_atp_page.html
git commit -m "feat: MCA ATP page PDF link discovery"
```

## Global constraints

- User-Agent for ALL HTTP requests must be exactly: `Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; +https://github.com/bcheevers123/id-rather-be-sailing)`
- Minimum 2-second delay between requests to the same domain (this task only makes one request to gov.uk)
- Never hardcode PDF URLs — always re-discover from the page
- Tests must use the saved HTML fixture, NOT live HTTP requests
- No fabricated course names or provider data

## Report file

Write your report to: `.superpowers/sdd/2026-08-03-maritime-training-plan/task-4-report.md`

Return only:
- Status: DONE / DONE_WITH_CONCERNS / BLOCKED
- Commits (hashes)
- Test summary (N passed, N failed)
- Any concerns (e.g., if live page structure differs from expected)
