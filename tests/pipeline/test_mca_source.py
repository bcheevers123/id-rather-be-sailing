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
