"""Response contract validation for factual answers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from src.config.settings import Settings, get_settings
from src.generation.refusal import AssistantResponse

MAX_SENTENCES = 3
FOOTER_PATTERN = re.compile(
    r"^Last updated from sources: \d{4}-\d{2}-\d{2}$",
)
_URL_PATTERN = re.compile(r"https?://[^\s\])>,]+")
_ADVICE_BLOCKLIST = re.compile(
    r"\b(recommend(?:ed|ation)?|should\s+invest|better|guaranteed|predict(?:ion|ed)?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...] = ()


def count_sentences(text: str) -> int:
    cleaned = text.strip()
    if not cleaned:
        return 0
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return len([part for part in parts if part.strip()])


def extract_urls(text: str) -> list[str]:
    return _URL_PATTERN.findall(text)


def _domain_allowed(url: str, allowed_domains: tuple[str, ...]) -> bool:
    hostname = urlparse(url).hostname or ""
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in allowed_domains)


def validate_answer(
    response: AssistantResponse,
    *,
    allowed_chunk_urls: tuple[str, ...],
    settings: Settings | None = None,
) -> ValidationResult:
    settings = settings or get_settings()
    errors: list[str] = []

    if response.type != "answer":
        errors.append("response type must be answer")

    sentence_count = count_sentences(response.text)
    if sentence_count > MAX_SENTENCES:
        errors.append(f"text exceeds {MAX_SENTENCES} sentences")

    text_urls = extract_urls(response.text)
    if text_urls:
        errors.append("text must not contain URLs")

    citation_url = response.citation.get("url", "")
    if not citation_url:
        errors.append("citation URL is required")
    elif not _domain_allowed(citation_url, settings.allowed_source_domains):
        errors.append("citation domain is not allowlisted")
    elif citation_url not in allowed_chunk_urls:
        errors.append("citation URL must match a retrieved chunk URL")

    if _ADVICE_BLOCKLIST.search(response.text):
        errors.append("text contains blocklisted advice language")

    if not FOOTER_PATTERN.match(response.footer):
        errors.append("footer format is invalid")

    if response.disclaimer != "Facts-only. No investment advice.":
        errors.append("disclaimer is missing or incorrect")

    return ValidationResult(valid=not errors, errors=tuple(errors))
