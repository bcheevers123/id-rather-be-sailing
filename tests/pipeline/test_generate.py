import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from pipeline.mca_source import PdfLink
from pipeline.pdf_parser import ParsedPdf, RawProvider, RawApproval


@patch("pipeline.generate.download_mca_page")
@patch("pipeline.generate.download_pdf")
@patch("pipeline.generate.fetch_pdf_links")
def test_run_pipeline_dry_run(mock_links, mock_download_pdf, mock_download_page, tmp_path):
    from pipeline.generate import run_pipeline

    mock_download_page.return_value = "<html></html>"
    mock_links.return_value = [
        PdfLink("Personal Survival Techniques", "https://example.com/pst.pdf", "stcw_basic")
    ]
    raw_provider = RawProvider(
        raw_name="Test Training Ltd",
        location="Kent",
        address="1 Test Street, Dover, Kent CT1 1AA",
        contact_details="Tel: 01234 567890\nEmail: test@test.com\nhttps://test.com/",
        not_open_to_public=False,
        is_uk=True,
    )
    mock_download_pdf.return_value = Path(tmp_path / "pst.pdf")

    with patch("pipeline.generate.parse_pdf") as mock_parse:
        mock_parse.return_value = ParsedPdf(
            providers=[raw_provider],
            approvals=[RawApproval("pst", "Test Training Ltd", "https://example.com/pst.pdf", "2026-07-16", False)],
        )
        run_pipeline(dry_run=True, output_dir=tmp_path)

    courses_file = tmp_path / "courses.json"
    assert courses_file.exists()
    courses = json.loads(courses_file.read_text())
    assert len(courses) >= 1
    assert courses[0]["id"] == "pst"

    providers_file = tmp_path / "providers.json"
    assert providers_file.exists()

    approvals_file = tmp_path / "approvals.json"
    assert approvals_file.exists()
