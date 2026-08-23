"""Tests for response contract validation."""

from __future__ import annotations

import pytest

from src.generation.generator import build_answer_response
from src.generation.validator import count_sentences, extract_urls, validate_answer
from src.retrieval.retriever import RetrievedChunk

CHUNK_URL = "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth"
OTHER_CHUNK_URL = "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"


def _sample_chunk(**overrides: object) -> RetrievedChunk:
    defaults = {
        "text": "Expense ratio\n1.03%",
        "score": 0.9,
        "scheme_id": "hdfc-large-cap-fund-direct-growth",
        "scheme_name": "HDFC Large Cap Fund Direct Growth",
        "page_or_section": "Fund overview",
        "source_url": CHUNK_URL,
        "document_date": "2026-08-21",
        "content_hash": "sha256:test",
    }
    defaults.update(overrides)
    return RetrievedChunk(**defaults)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("One sentence.", 1),
        ("First sentence. Second sentence.", 2),
        ("First! Second? Third.", 3),
        ("", 0),
    ],
)
def test_count_sentences(text: str, expected: int) -> None:
    assert count_sentences(text) == expected


def test_extract_urls() -> None:
    text = "See https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth for details."
    assert extract_urls(text) == [
        "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth"
    ]


def test_validate_answer_accepts_valid_response() -> None:
    response = build_answer_response(
        "The direct plan carries an expense ratio of 1.03%. "
        "This is listed on the Groww scheme page.",
        _sample_chunk(),
    )
    result = validate_answer(response, allowed_chunk_urls=(CHUNK_URL,))
    assert result.valid is True
    assert result.errors == ()


def test_validate_answer_rejects_too_many_sentences() -> None:
    response = build_answer_response(
        "One. Two. Three. Four.",
        _sample_chunk(),
    )
    result = validate_answer(response, allowed_chunk_urls=(CHUNK_URL,))
    assert result.valid is False
    assert any("sentences" in error for error in result.errors)


def test_validate_answer_rejects_url_in_text() -> None:
    response = build_answer_response(
        f"See {CHUNK_URL} for details.",
        _sample_chunk(),
    )
    result = validate_answer(response, allowed_chunk_urls=(CHUNK_URL,))
    assert result.valid is False
    assert any("URLs" in error for error in result.errors)


def test_validate_answer_rejects_bad_citation_domain() -> None:
    response = build_answer_response(
        "The expense ratio is 1.03%.",
        _sample_chunk(source_url="https://example.com/fund"),
    )
    result = validate_answer(response, allowed_chunk_urls=("https://example.com/fund",))
    assert result.valid is False
    assert any("allowlisted" in error for error in result.errors)


def test_validate_answer_rejects_citation_not_in_chunks() -> None:
    response = build_answer_response(
        "The expense ratio is 1.03%.",
        _sample_chunk(),
    )
    result = validate_answer(response, allowed_chunk_urls=(OTHER_CHUNK_URL,))
    assert result.valid is False
    assert any("retrieved chunk" in error for error in result.errors)


@pytest.mark.parametrize(
    "text",
    [
        "I recommend investing in this fund.",
        "You should invest now.",
        "This fund is better than others.",
        "Returns are guaranteed.",
        "I predict strong growth.",
    ],
)
def test_validate_answer_rejects_advice_language(text: str) -> None:
    response = build_answer_response(text, _sample_chunk())
    result = validate_answer(response, allowed_chunk_urls=(CHUNK_URL,))
    assert result.valid is False
    assert any("blocklisted" in error for error in result.errors)


def test_validate_answer_rejects_invalid_footer() -> None:
    chunk = _sample_chunk()
    response = build_answer_response("The expense ratio is 1.03%.", chunk)
    response = response.__class__(
        type=response.type,
        text=response.text,
        citation=response.citation,
        footer="Updated yesterday",
        disclaimer=response.disclaimer,
    )
    result = validate_answer(response, allowed_chunk_urls=(CHUNK_URL,))
    assert result.valid is False
    assert any("footer" in error for error in result.errors)


def test_validate_answer_rejects_missing_disclaimer() -> None:
    chunk = _sample_chunk()
    response = build_answer_response("The expense ratio is 1.03%.", chunk)
    response = response.__class__(
        type=response.type,
        text=response.text,
        citation=response.citation,
        footer=response.footer,
        disclaimer="No disclaimer",
    )
    result = validate_answer(response, allowed_chunk_urls=(CHUNK_URL,))
    assert result.valid is False
    assert any("disclaimer" in error for error in result.errors)
