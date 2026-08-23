"""Tests for Groq primary-model rate limiting."""

from __future__ import annotations

import time

import pytest

from src.generation.rate_limiter import (
    GroqRateLimitExceeded,
    GroqRateLimiter,
    ModelRateLimits,
    estimate_tokens,
    reset_primary_rate_limiter,
)


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    reset_primary_rate_limiter()
    yield
    reset_primary_rate_limiter()


def test_estimate_tokens_includes_output_budget() -> None:
    estimate = estimate_tokens("system", "user question", max_output_tokens=128)
    assert estimate >= 128


def test_wait_for_capacity_allows_under_limit() -> None:
    limiter = GroqRateLimiter(ModelRateLimits(rpm=30, rpd=1000, tpm=8000, tpd=200_000))
    limiter.wait_for_capacity(500)
    limiter.record(500)
    assert limiter.snapshot()["requests_last_minute"] == 1


def test_daily_request_limit_raises() -> None:
    limiter = GroqRateLimiter(ModelRateLimits(rpm=30, rpd=2, tpm=8000, tpd=200_000))
    limiter.record(100)
    limiter.record(100)
    with pytest.raises(GroqRateLimitExceeded, match="Daily"):
        limiter.wait_for_capacity(100)


def test_daily_token_limit_raises() -> None:
    limiter = GroqRateLimiter(ModelRateLimits(rpm=30, rpd=1000, tpm=8000, tpd=300))
    limiter.record(250)
    with pytest.raises(GroqRateLimitExceeded, match="Daily"):
        limiter.wait_for_capacity(100)


def test_minute_request_limit_waits_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    current = {"t": 1_000.0}

    def fake_time() -> float:
        return current["t"]

    def fake_sleep(seconds: float) -> None:
        current["t"] += seconds

    monkeypatch.setattr(time, "time", fake_time)
    monkeypatch.setattr(time, "sleep", fake_sleep)

    limiter = GroqRateLimiter(
        ModelRateLimits(rpm=1, rpd=1000, tpm=8000, tpd=200_000),
        max_wait_seconds=65.0,
    )
    limiter.record(100)
    limiter.wait_for_capacity(100)
    limiter.record(100)
    assert limiter.snapshot()["requests_last_minute"] == 1


def test_minute_request_limit_raises_when_wait_exceeded() -> None:
    limiter = GroqRateLimiter(
        ModelRateLimits(rpm=1, rpd=1000, tpm=8000, tpd=200_000),
        max_wait_seconds=0.1,
    )
    limiter.record(100)
    with pytest.raises(GroqRateLimitExceeded, match="per-minute"):
        limiter.wait_for_capacity(100)
