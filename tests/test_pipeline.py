"""Tests for the end-to-end RAG pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.config.settings import REFUSAL_CITATION_URL, get_settings
from src.generation.generator import Generator
from src.generation.pipeline import Pipeline
from src.generation.rate_limiter import GroqRateLimitExceeded
from src.generation.refusal import DISCLAIMER
from src.generation.validator import validate_answer
from src.retrieval.retriever import Retriever

EVAL_PATH = Path(__file__).parent / "eval_set.json"


@pytest.fixture
def eval_set() -> dict:
    with open(EVAL_PATH, encoding="utf-8") as handle:
        return json.load(handle)


class _MockGroqClient:
    def __init__(self, responses: list[str] | None = None) -> None:
        self.responses = list(responses or [])
        self.calls = 0

    def chat(self, **kwargs: object) -> str:
        if self.responses:
            self.calls += 1
            return self.responses.pop(0)
        system = kwargs.get("system", "")
        user = kwargs.get("user", "")
        if "1.03%" in user:
            return "The expense ratio of HDFC Large Cap Fund Direct Growth is 1.03%."
        if "₹100" in user and "Mid Cap" in user:
            return "The minimum SIP for HDFC Mid Cap Fund Direct Growth is ₹100."
        return "The requested fact is available on the Groww scheme page."


def _pipeline_with_mock(
    retriever: Retriever,
    responses: list[str] | None = None,
) -> Pipeline:
    mock_client = _MockGroqClient(responses)
    generator = Generator(groq_client=mock_client)  # type: ignore[arg-type]
    return Pipeline(retriever=retriever, generator=generator)


@pytest.mark.parametrize(
    "query",
    [
        "Should I invest in this fund?",
        "Which fund is better?",
        "What returns will I get if I invest 10k?",
    ],
)
def test_pipeline_refuses_advisory(indexed_retriever: Retriever, query: str) -> None:
    pipeline = _pipeline_with_mock(indexed_retriever)
    response = pipeline.answer_query(query)
    assert response.type == "refusal"
    assert response.citation["url"] == REFUSAL_CITATION_URL
    assert response.disclaimer == DISCLAIMER


def test_pipeline_low_confidence_off_topic(indexed_retriever: Retriever) -> None:
    pipeline = _pipeline_with_mock(indexed_retriever)
    response = pipeline.answer_query("Who is the CEO of Groww?")
    assert response.type in {"refusal", "answer"}
    if response.type == "answer":
        assert "groww.in" in response.citation["url"]


def test_pipeline_generates_valid_answer_with_mock(indexed_retriever: Retriever) -> None:
    pipeline = _pipeline_with_mock(
        indexed_retriever,
        responses=[
            "The expense ratio of HDFC Large Cap Fund Direct Growth is 1.03%.",
        ],
    )
    response = pipeline.answer_query(
        "What is the expense ratio of HDFC Large Cap Fund Direct Growth?"
    )
    assert response.type == "answer"
    assert "1.03%" in response.text or "1.03" in response.text
    assert response.citation["url"].startswith("https://groww.in/mutual-funds/")
    assert response.footer == "Last updated from sources: 2026-08-21"
    assert response.disclaimer == DISCLAIMER

    retrieval = indexed_retriever.retrieve(
        "What is the expense ratio of HDFC Large Cap Fund Direct Growth?"
    )
    chunk_urls = tuple(chunk.source_url for chunk in retrieval.chunks)
    validation = validate_answer(response, allowed_chunk_urls=chunk_urls)
    assert validation.valid is True


def test_pipeline_retries_then_fallback(indexed_retriever: Retriever) -> None:
    pipeline = _pipeline_with_mock(
        indexed_retriever,
        responses=[
            "One. Two. Three. Four.",
            "One. Two. Three. Four.",
        ],
    )
    response = pipeline.answer_query(
        "What is the expense ratio of HDFC Large Cap Fund Direct Growth?"
    )
    assert response.type == "answer"
    assert "couldn't find verified information" in response.text.lower()
    assert response.citation["url"].startswith("https://groww.in/")


def test_pipeline_rate_limit_falls_back(indexed_retriever: Retriever) -> None:
    class _RateLimitedClient:
        def chat(self, **kwargs: object) -> str:
            raise GroqRateLimitExceeded("Daily Groq quota exhausted")

    generator = Generator(groq_client=_RateLimitedClient())  # type: ignore[arg-type]
    pipeline = Pipeline(retriever=indexed_retriever, generator=generator)
    response = pipeline.answer_query(
        "What is the expense ratio of HDFC Large Cap Fund Direct Growth?"
    )
    assert response.type == "answer"
    assert "couldn't find verified information" in response.text.lower()
    assert response.citation["url"].startswith("https://groww.in/mutual-funds/")


def test_eval_advisory_cases(indexed_retriever: Retriever, eval_set: dict) -> None:
    pipeline = _pipeline_with_mock(indexed_retriever)
    for case in eval_set["advisory"]:
        response = pipeline.answer_query(case["query"])
        assert response.type == "refusal", case["query"]


def test_eval_factual_retrieval_grounding(indexed_retriever: Retriever, eval_set: dict) -> None:
    """Verify retrieval returns chunks containing expected facts (no LLM required)."""
    passed = 0
    for case in eval_set["factual"]:
        result = indexed_retriever.retrieve(case["query"])
        assert not result.low_confidence, case["query"]
        combined = "\n".join(chunk.text for chunk in result.chunks)
        if case["expected_fact"] in combined:
            passed += 1
        assert result.chunks[0].scheme_id == case["scheme_id"], case["query"]
    assert passed >= 16


@pytest.mark.integration
def test_groq_connectivity() -> None:
    settings = get_settings()
    if not settings.groq_api_key:
        pytest.skip("GROQ_API_KEY not set")

    from src.generation.groq_client import GroqClient

    client = GroqClient(settings)
    assert client.check_connectivity() is True


@pytest.mark.integration
def test_pipeline_end_to_end(indexed_retriever: Retriever) -> None:
    settings = get_settings()
    if not settings.groq_api_key:
        pytest.skip("GROQ_API_KEY not set")

    pipeline = Pipeline(retriever=indexed_retriever)
    response = pipeline.answer_query(
        "What is the expense ratio of HDFC Large Cap Fund Direct Growth?"
    )
    assert response.type == "answer"
    assert response.citation["url"].startswith("https://groww.in/")
    assert response.disclaimer == DISCLAIMER
