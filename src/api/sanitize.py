"""Input sanitization for chat requests."""

from __future__ import annotations

import re

from src.generation.classifier import contains_pii
from src.generation.refusal import AssistantResponse, build_refusal

MAX_MESSAGE_LENGTH = 2000
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _HTML_TAG_PATTERN.sub("", text)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def sanitize_message(message: str) -> tuple[str, AssistantResponse | None]:
    """Sanitize user input and reject PII before the RAG pipeline runs."""
    cleaned = _normalize_whitespace(_strip_html(message))
    if not cleaned:
        return "", build_refusal("out_of_scope")

    if contains_pii(cleaned):
        return cleaned, build_refusal("pii")

    if len(cleaned) > MAX_MESSAGE_LENGTH:
        cleaned = cleaned[:MAX_MESSAGE_LENGTH].rstrip()

    return cleaned, None
