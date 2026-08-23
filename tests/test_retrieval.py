"""Tests for scheme resolution, section routing, and retrieval."""

from __future__ import annotations

import pytest

from src.ingestion.indexer import collection_count, index_chunks, rebuild_index
from src.retrieval.retriever import Retriever
from src.retrieval.scheme_resolver import resolve_scheme
from src.retrieval.section_router import FUND_HOUSE_SECTION, route_section


@pytest.mark.parametrize(
    ("query", "expected_scheme_id", "expected_confidence"),
    [
        (
            "What is the expense ratio of HDFC Large Cap Fund Direct Growth?",
            "hdfc-large-cap-fund-direct-growth",
            "exact",
        ),
        ("HDFC Mid Cap minimum SIP amount", "hdfc-mid-cap-fund-direct-growth", "partial"),
        ("exit load on HDFC Gold ETF FoF", "hdfc-gold-etf-fund-of-fund-direct-plan-growth", "partial"),
        ("ELSS lock-in period HDFC Tax Saver", "hdfc-elss-tax-saver-fund-direct-plan-growth", "partial"),
        ("benchmark for HDFC Small Cap Fund", "hdfc-small-cap-fund-direct-growth", "partial"),
    ],
)
def test_resolve_scheme(query: str, expected_scheme_id: str, expected_confidence: str) -> None:
    match = resolve_scheme(query)
    assert match.scheme_id == expected_scheme_id
    assert match.confidence == expected_confidence


def test_resolve_scheme_none() -> None:
    match = resolve_scheme("minimum SIP")
    assert match.scheme_id is None
    assert match.confidence == "none"


@pytest.mark.parametrize(
    ("query", "expected_section"),
    [
        ("What is the expense ratio of HDFC Large Cap?", "Fund overview"),
        ("HDFC Mid Cap minimum SIP amount", "Minimum investments"),
        ("exit load on HDFC Gold ETF FoF", "Exit load, stamp duty and tax"),
        ("ELSS lock-in period", "ELSS lock-in"),
        ("benchmark for HDFC Small Cap Fund", "Investment objective and benchmark"),
    ],
)
def test_route_section(query: str, expected_section: str) -> None:
    route = route_section(query)
    assert route.page_or_section == expected_section
    assert route.confidence == "high"
    assert route.is_faq_fact is True


def test_route_section_fund_house_not_faq() -> None:
    route = route_section("Who is the registrar for the fund house?")
    assert route.page_or_section == FUND_HOUSE_SECTION
    assert route.is_faq_fact is False


@pytest.mark.parametrize(
    ("query", "expected_scheme_id", "expected_section", "expected_snippet"),
    [
        (
            "What is the expense ratio of HDFC Large Cap Fund Direct Growth?",
            "hdfc-large-cap-fund-direct-growth",
            "Fund overview",
            "1.03%",
        ),
        (
            "HDFC Mid Cap minimum SIP amount",
            "hdfc-mid-cap-fund-direct-growth",
            "Minimum investments",
            "₹100",
        ),
        (
            "exit load on HDFC Gold ETF FoF",
            "hdfc-gold-etf-fund-of-fund-direct-plan-growth",
            "Exit load, stamp duty and tax",
            "15 days",
        ),
        (
            "ELSS lock-in period HDFC Tax Saver",
            "hdfc-elss-tax-saver-fund-direct-plan-growth",
            "ELSS lock-in",
            "3Y Lock-in",
        ),
        (
            "benchmark for HDFC Small Cap Fund",
            "hdfc-small-cap-fund-direct-growth",
            "Investment objective and benchmark",
            "BSE 250 SmallCap",
        ),
        (
            "What is the exit load on HDFC ELSS?",
            "hdfc-elss-tax-saver-fund-direct-plan-growth",
            "Exit load, stamp duty and tax",
            "Nil",
        ),
    ],
)
def test_retriever_manual_queries(
    indexed_retriever: Retriever,
    query: str,
    expected_scheme_id: str,
    expected_section: str,
    expected_snippet: str,
) -> None:
    result = indexed_retriever.retrieve(query)
    assert result.chunks, f"No chunks returned for: {query}"
    top = result.chunks[0]
    assert top.scheme_id == expected_scheme_id
    assert top.page_or_section == expected_section
    assert expected_snippet in top.text


def test_retriever_needs_disambiguation(indexed_retriever: Retriever) -> None:
    result = indexed_retriever.retrieve("minimum SIP")
    assert result.needs_disambiguation is True


def test_retriever_low_confidence_off_topic(indexed_retriever: Retriever) -> None:
    result = indexed_retriever.retrieve("who is the CEO of Groww")
    assert result.low_confidence is True


def test_retriever_faq_never_returns_fund_house(indexed_retriever: Retriever) -> None:
    queries = [
        "expense ratio HDFC Large Cap Fund Direct Growth",
        "minimum SIP HDFC Mid Cap",
        "exit load HDFC Small Cap",
        "benchmark HDFC ELSS Tax Saver",
    ]
    for query in queries:
        result = indexed_retriever.retrieve(query)
        assert result.chunks[0].page_or_section != FUND_HOUSE_SECTION, query


def test_reindex_does_not_duplicate(indexed_retriever: Retriever) -> None:
    second = index_chunks(rebuild=False)
    assert second.indexed_count == 0
    assert second.skipped_count == 31
    assert collection_count() == 31


def test_shared_content_hash_stays_scheme_scoped(indexed_retriever: Retriever) -> None:
    result = indexed_retriever.retrieve("minimum SIP HDFC Large Cap Fund Direct Growth")
    assert result.chunks[0].scheme_id == "hdfc-large-cap-fund-direct-growth"
    assert result.chunks[0].page_or_section == "Minimum investments"

    result = indexed_retriever.retrieve("minimum SIP HDFC ELSS Tax Saver Fund Direct Plan Growth")
    assert result.chunks[0].scheme_id == "hdfc-elss-tax-saver-fund-direct-plan-growth"
    assert "₹500" in result.chunks[0].text
