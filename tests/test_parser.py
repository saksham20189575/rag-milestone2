from pathlib import Path

import pytest

from src.ingestion.parser import (
    DEFAULT_DOC_ID,
    MIN_TEXT_LENGTH,
    extract_document_date,
    normalize_text,
    parse_html,
    parse_scheme_page,
)


def test_normalize_text_collapses_whitespace() -> None:
    raw = "Expense ratio\u00a0  1.03%\n\n\n\nExit load\n  1%"
    assert normalize_text(raw) == "Expense ratio 1.03%\n\nExit load\n1%"


@pytest.mark.parametrize(
    "html,expected",
    [
        ("NAV as of 21 Aug 2026", "2026-08-21"),
        ("NAV of HDFC Large Cap Fund Direct Growth is ₹1,245.13 as of 21 Aug 2026", "2026-08-21"),
        ('{"dateModified":"2025-07-31T10:00:00Z"}', "2025-07-31"),
    ],
)
def test_extract_document_date(html: str, expected: str) -> None:
    assert extract_document_date(html) == expected


def test_extract_document_date_falls_back_to_fetch_timestamp() -> None:
    assert extract_document_date("<html></html>", fallback="2026-08-23T06:02:42Z") == "2026-08-23"


def test_parse_html_from_saved_large_cap_page() -> None:
    html_path = Path("data/raw/hdfc-large-cap-fund-direct-growth/page.html")
    if not html_path.exists():
        pytest.skip("raw HTML not fetched yet")

    html = html_path.read_text(encoding="utf-8")
    text, document_date, method = parse_html(html, allow_playwright=False)

    assert len(text) > MIN_TEXT_LENGTH
    assert "Expense ratio" in text
    assert "Exit load" in text
    assert "Fund benchmark" in text or "NIFTY 100" in text
    assert document_date == "2026-08-21"
    assert method == "beautifulsoup+trafilatura"


def test_parse_scheme_page_writes_processed_files() -> None:
    html_path = Path("data/raw/hdfc-large-cap-fund-direct-growth/page.html")
    if not html_path.exists():
        pytest.skip("raw HTML not fetched yet")

    scheme = {
        "scheme_id": "hdfc-large-cap-fund-direct-growth",
        "scheme_name": "HDFC Large Cap Fund Direct Growth",
        "category": "Large-cap",
        "source_url": "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
    }
    result = parse_scheme_page(scheme, allow_playwright=False)

    assert result.doc_id == DEFAULT_DOC_ID
    assert result.text_path.exists()
    assert result.metadata_path.exists()
    assert result.text_path.read_text(encoding="utf-8").strip()
    assert result.document_date is not None
