"""Tests for Groq client helpers."""

from __future__ import annotations

from src.generation.groq_client import clean_model_output, effective_max_tokens


def test_clean_model_output_strips_redacted_thinking() -> None:
    raw = (
        "\n<think>internal reasoning</think>\n\n"
        "factual"
    )
    assert clean_model_output(raw) == "factual"


def test_clean_model_output_strips_think_tags() -> None:
    raw = f"{chr(60)}think{chr(62)}internal reasoning{chr(60)}/think{chr(62)}\n\nOK"
    assert clean_model_output(raw) == "OK"


def test_effective_max_tokens_for_reasoning_models() -> None:
    assert effective_max_tokens("qwen/qwen3.6-27b", 16) == 512
    assert effective_max_tokens("openai/gpt-oss-20b", 16) == 64
    assert effective_max_tokens("some-other-model", 16) == 16
