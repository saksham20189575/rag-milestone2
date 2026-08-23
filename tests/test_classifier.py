"""Tests for query classification and refusal handling."""

from __future__ import annotations

from datetime import date

import pytest

from src.config.settings import REFUSAL_CITATION_URL
from src.generation.classifier import classify_query
from src.generation.refusal import DISCLAIMER, build_refusal, classify_and_refuse

ADVISORY_QUERIES = [
    "Should I invest in this fund?",
    "Do you recommend HDFC Large Cap Fund?",
    "Is this fund worth investing in?",
    "Should I buy or sell HDFC Mid Cap?",
    "Would you recommend this fund for retirement?",
    "Is HDFC ELSS a good investment?",
    "Should I switch to HDFC Small Cap Fund?",
    "Can you advise me on investing in this scheme?",
    "Tell me if I should invest 10k in this fund",
    "Is it a good idea to invest in HDFC Gold ETF FoF?",
]

COMPARATIVE_QUERIES = [
    "Which fund is better?",
    "What is the best HDFC fund?",
    "Compare HDFC Large Cap vs HDFC Mid Cap",
    "HDFC Small Cap versus HDFC Mid Cap",
]

PERFORMANCE_QUERIES = [
    "What returns will I get if I invest 10k?",
    "What is the CAGR if I invest 5000 per month?",
    "How much will I earn if I invest in HDFC Large Cap?",
    "Predict my returns for HDFC Mid Cap",
    "Calculate my returns on 1 lakh in HDFC ELSS",
]

FACTUAL_QUERIES = [
    "What is the expense ratio of HDFC Large Cap Fund Direct Growth?",
    "What is the exit load on HDFC Mid Cap Fund Direct Growth?",
    "HDFC Mid Cap minimum SIP amount",
    "ELSS lock-in period HDFC Tax Saver",
    "benchmark for HDFC Small Cap Fund",
    "What is the minimum SIP for HDFC ELSS?",
    "What is the expense ratio of HDFC Gold ETF FoF?",
    "What is the exit load on HDFC ELSS?",
    "What is the riskometer for HDFC Large Cap Fund?",
    "What is the fund size of HDFC Mid Cap Fund?",
]

PII_QUERIES = [
    ("My PAN is ABCDE1234F, check my balance", "pii"),
    ("My email is user@example.com", "pii"),
    ("Call me at 9876543210 about my SIP", "pii"),
    ("My Aadhaar is 1234 5678 9012", "pii"),
]

OUT_OF_SCOPE_QUERIES = [
    "Who is the CEO of Groww?",
    "What is the weather in Mumbai?",
    "Tell me a joke about stocks",
]


@pytest.mark.parametrize("query", ADVISORY_QUERIES)
def test_advisory_queries_refused(query: str) -> None:
    result = classify_query(query)
    assert result.intent == "advisory"
    assert result.method == "rule"

    refusal = classify_and_refuse(query, as_of=date(2026, 8, 23))
    assert refusal is not None
    assert refusal.type == "refusal"
    assert refusal.citation["url"] == REFUSAL_CITATION_URL
    assert refusal.disclaimer == DISCLAIMER
    assert "Last updated from sources: 2026-08-23" in refusal.footer


@pytest.mark.parametrize("query", COMPARATIVE_QUERIES)
def test_comparative_queries_refused(query: str) -> None:
    result = classify_query(query)
    assert result.intent == "comparative"

    refusal = classify_and_refuse(query)
    assert refusal is not None
    assert refusal.citation["url"] == REFUSAL_CITATION_URL


@pytest.mark.parametrize("query", PERFORMANCE_QUERIES)
def test_performance_queries_refused(query: str) -> None:
    result = classify_query(query)
    assert result.intent == "performance"

    refusal = classify_and_refuse(query)
    assert refusal is not None
    assert refusal.citation["url"] == REFUSAL_CITATION_URL


@pytest.mark.parametrize("query", FACTUAL_QUERIES)
def test_factual_queries_not_refused(query: str) -> None:
    result = classify_query(query)
    assert result.intent == "factual", f"Unexpected refusal for: {query!r}"

    refusal = classify_and_refuse(query)
    assert refusal is None


@pytest.mark.parametrize("query,expected_intent", PII_QUERIES)
def test_pii_queries_blocked(query: str, expected_intent: str) -> None:
    result = classify_query(query)
    assert result.intent == expected_intent
    assert result.method == "rule"

    refusal = classify_and_refuse(query)
    assert refusal is not None
    assert refusal.intent == "pii"
    assert refusal.citation["url"] == REFUSAL_CITATION_URL


@pytest.mark.parametrize("query", OUT_OF_SCOPE_QUERIES)
def test_out_of_scope_queries(query: str) -> None:
    result = classify_query(query)
    assert result.intent == "out_of_scope"

    refusal = classify_and_refuse(query)
    assert refusal is not None
    assert refusal.type == "refusal"


def test_refusal_includes_exactly_one_groww_citation() -> None:
    for intent in ("advisory", "comparative", "performance", "pii", "out_of_scope"):
        refusal = build_refusal(intent)
        assert refusal.citation["url"] == REFUSAL_CITATION_URL
        assert refusal.citation["url"].count("groww.in") == 1
        assert "groww.in/p/mutual-funds" in refusal.citation["url"]


def test_problem_statement_refusal_cases() -> None:
    cases = [
        ("Should I invest in this fund?", "advisory"),
        ("Which fund is better?", "comparative"),
        ("What returns will I get if I invest 10k?", "performance"),
    ]
    for query, expected_intent in cases:
        result = classify_query(query)
        assert result.intent == expected_intent
        refusal = classify_and_refuse(query)
        assert refusal is not None
        assert refusal.citation["url"] == REFUSAL_CITATION_URL


def test_factual_does_not_build_refusal() -> None:
    with pytest.raises(ValueError, match="factual"):
        build_refusal("factual")
