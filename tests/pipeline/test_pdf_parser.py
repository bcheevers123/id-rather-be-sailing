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
