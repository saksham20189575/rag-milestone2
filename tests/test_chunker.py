from pathlib import Path

import pytest

from src.config.settings import load_schemes
from src.ingestion.chunker import (
    CHUNKS_FILENAME,
    cleanup_lines,
    content_hash,
    chunk_document,
    chunk_schemes,
    estimate_tokens,
    extract_sections,
    load_chunks,
)


@pytest.fixture
def scheme_registry() -> list[dict]:
    return load_schemes()


def test_estimate_tokens() -> None:
    text = "Expense ratio 1.03% for HDFC Large Cap Fund Direct Growth"
    assert estimate_tokens(text) >= 5


def test_cleanup_lines_trims_nav_and_footer() -> None:
    lines = [
        "Stocks",
        "Invest in Stocks",
        "HDFC Large Cap Fund Direct Growth",
        "Expense ratio",
        "1.03%",
        "Home >",
        "Mutual Funds",
    ]
    cleaned = cleanup_lines(lines, "HDFC Large Cap Fund Direct Growth")
    assert cleaned[0] == "HDFC Large Cap Fund Direct Growth"
    assert "Home >" not in cleaned


def test_extract_sections_large_cap() -> None:
    text_path = Path("data/processed/hdfc-large-cap-fund-direct-growth/groww_scheme_page.txt")
    if not text_path.exists():
        pytest.skip("processed text not available")

    scheme = next(s for s in load_schemes() if s["scheme_id"] == "hdfc-large-cap-fund-direct-growth")
    sections = dict(extract_sections(text_path.read_text(encoding="utf-8").splitlines(), scheme))

    assert "Fund overview" in sections
    assert "Expense ratio" in sections["Fund overview"]
    assert "Minimum investments" in sections
    assert "Exit load, stamp duty and tax" in sections
    assert "About the fund" in sections
    assert "Investment objective and benchmark" in sections
    assert "Fund benchmark" in sections["Investment objective and benchmark"]
    assert "Fund house" in sections
    assert "Holdings (" not in "\n".join(sections.values())
    assert "Compare similar funds" not in "\n".join(sections.values())


def test_chunk_schemes_produces_required_facts(scheme_registry: list[dict]) -> None:
    text_path = Path("data/processed/hdfc-large-cap-fund-direct-growth/groww_scheme_page.txt")
    if not text_path.exists():
        pytest.skip("processed text not available")

    results = chunk_schemes(scheme_ids={s["scheme_id"] for s in scheme_registry})
    assert len(results) == 5

    for scheme in scheme_registry:
        chunks = load_chunks(scheme["scheme_id"])
        corpus = "\n".join(chunk.text for chunk in chunks)
        assert any("Expense ratio" in chunk.text for chunk in chunks)
        assert any("Exit load" in chunk.text for chunk in chunks)
        assert any("Fund benchmark" in chunk.text or "benchmark" in chunk.text.lower() for chunk in chunks)
        assert "Holdings (" not in corpus
        assert "Compare similar funds" not in corpus
        assert 5 <= len(chunks) <= 10


def test_elss_chunk_contains_lock_in() -> None:
    text_path = Path("data/processed/hdfc-elss-tax-saver-fund-direct-plan-growth/groww_scheme_page.txt")
    if not text_path.exists():
        pytest.skip("processed text not available")

    chunk_schemes(scheme_ids={"hdfc-elss-tax-saver-fund-direct-plan-growth"})
    chunks = load_chunks("hdfc-elss-tax-saver-fund-direct-plan-growth")
    corpus = "\n".join(chunk.text for chunk in chunks)
    assert "Lock-in" in corpus or "lock-in" in corpus


def test_chunk_document_writes_jsonl() -> None:
    text_path = Path("data/processed/hdfc-large-cap-fund-direct-growth/groww_scheme_page.txt")
    if not text_path.exists():
        pytest.skip("processed text not available")

    scheme = next(s for s in load_schemes() if s["scheme_id"] == "hdfc-large-cap-fund-direct-growth")
    result = chunk_document(scheme)
    assert result.chunks_path.exists()
    assert result.chunks_path.name == CHUNKS_FILENAME
    assert result.chunk_count >= 5

    first = load_chunks(scheme["scheme_id"])[0]
    assert first.metadata["document_type"] == "groww_scheme_page"
    assert first.metadata["source_url"].startswith("https://groww.in/")
    assert first.metadata["content_hash"].startswith("sha256:")
    assert first.metadata["page_or_section"]
    assert estimate_tokens(first.text) <= 650


def test_content_hash_deduplicates_identical_text() -> None:
    text = "Expense ratio\n1.03%"
    assert content_hash(text) == content_hash(text)
    assert content_hash(text) != content_hash("Expense ratio\n1.04%")
