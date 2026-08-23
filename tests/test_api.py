"""Integration tests for the FastAPI chat endpoints."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.deps import get_pipeline, reset_pipeline
from src.api.main import app
from src.api.rate_limit import REQUESTS_PER_MINUTE, reset_rate_limits
from src.config.settings import REFUSAL_CITATION_URL
from src.generation.generator import Generator
from src.generation.pipeline import Pipeline
from src.generation.refusal import DISCLAIMER
from src.retrieval.retriever import Retriever


@pytest.fixture(autouse=True)
def _reset_api_state() -> None:
    reset_rate_limits()
    reset_pipeline()
    app.dependency_overrides.clear()
    yield
    reset_rate_limits()
    reset_pipeline()
    app.dependency_overrides.clear()


@pytest.fixture
def pipeline(indexed_retriever: Retriever) -> Pipeline:
    return Pipeline(retriever=indexed_retriever)


@pytest.fixture
def client(pipeline: Pipeline) -> TestClient:
    app.dependency_overrides[get_pipeline] = lambda: pipeline
    return TestClient(app)


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_schemes(client: TestClient) -> None:
    response = client.get("/schemes")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["schemes"]) == 5
    assert payload["schemes"][0]["scheme_id"]
    assert payload["schemes"][0]["source_url"].startswith("https://groww.in/")


def test_chat_missing_message(client: TestClient) -> None:
    response = client.post("/chat", json={})
    assert response.status_code == 422


def test_chat_invalid_json(client: TestClient) -> None:
    response = client.post("/chat", content="not-json", headers={"Content-Type": "application/json"})
    assert response.status_code == 422


def test_chat_strips_html(client: TestClient, pipeline: Pipeline) -> None:
    class _MockGroqClient:
        def chat(self, **kwargs: object) -> str:
            return "The expense ratio of HDFC Large Cap Fund Direct Growth is 1.03%."

    app.dependency_overrides[get_pipeline] = lambda: Pipeline(
        retriever=pipeline.retriever,
        generator=Generator(groq_client=_MockGroqClient()),  # type: ignore[arg-type]
    )
    response = client.post(
        "/chat",
        json={"message": "<script>alert(1)</script>What is the expense ratio of HDFC Large Cap Fund Direct Growth?"},
    )
    assert response.status_code == 200
    assert response.json()["type"] == "answer"


def test_chat_rejects_pii(client: TestClient) -> None:
    response = client.post(
        "/chat",
        json={"message": "My PAN is ABCDE1234F, what is the expense ratio?"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "refusal"
    assert payload["intent"] == "pii"
    assert payload["citation"]["url"] == REFUSAL_CITATION_URL


def test_chat_refuses_advisory(client: TestClient) -> None:
    response = client.post("/chat", json={"message": "Should I invest in this fund?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "refusal"
    assert payload["citation"]["url"] == REFUSAL_CITATION_URL
    assert payload["disclaimer"] == DISCLAIMER


def test_chat_factual_answer(client: TestClient, pipeline: Pipeline) -> None:
    class _MockGroqClient:
        def chat(self, **kwargs: object) -> str:
            return "The expense ratio of HDFC Large Cap Fund Direct Growth is 1.03%."

    app.dependency_overrides[get_pipeline] = lambda: Pipeline(
        retriever=pipeline.retriever,
        generator=Generator(groq_client=_MockGroqClient()),  # type: ignore[arg-type]
    )
    response = client.post(
        "/chat",
        json={"message": "What is the expense ratio of HDFC Large Cap Fund Direct Growth?"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "answer"
    assert "1.03" in payload["text"]
    assert payload["citation"]["url"].startswith("https://groww.in/mutual-funds/")
    assert payload["footer"] == "Last updated from sources: 2026-08-21"
    assert payload["disclaimer"] == DISCLAIMER


def test_chat_truncates_long_message(client: TestClient) -> None:
    long_prefix = "x" * 2500
    response = client.post(
        "/chat",
        json={"message": f"{long_prefix} expense ratio HDFC Large Cap Fund Direct Growth"},
    )
    assert response.status_code == 200


def test_chat_rate_limit(client: TestClient) -> None:
    for _ in range(REQUESTS_PER_MINUTE):
        response = client.post("/chat", json={"message": "Should I invest in this fund?"})
        assert response.status_code == 200

    response = client.post("/chat", json={"message": "Should I invest in this fund?"})
    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_chat_index_missing(client: TestClient) -> None:
    with patch("src.api.deps.collection_count", return_value=0):
        response = client.post(
            "/chat",
            json={"message": "What is the expense ratio of HDFC Large Cap Fund Direct Growth?"},
        )
    assert response.status_code == 503
