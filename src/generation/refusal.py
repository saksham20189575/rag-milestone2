"""Compliant refusal responses for non-factual query intents."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from src.config.settings import get_settings
from src.generation.classifier import ClassificationResult, Intent, classify_query

DISCLAIMER = "Facts-only. No investment advice."

_REFUSAL_TEMPLATES: dict[Intent, str] = {
    "advisory": (
        "I can only answer factual questions about mutual fund schemes and cannot "
        "provide investment advice or recommendations. For general guidance on "
        "mutual funds, please refer to Groww's investor resources."
    ),
    "comparative": (
        "I cannot compare mutual fund schemes or suggest which fund is better. "
        "I can only share objective facts from official sources. For general "
        "guidance on mutual funds, please refer to Groww's investor resources."
    ),
    "performance": (
        "I cannot calculate or predict investment returns. For performance "
        "information, please refer to the official Groww scheme page or Groww's "
        "investor resources."
    ),
    "pii": (
        "I cannot process personal or account information such as PAN, Aadhaar, "
        "email, or phone numbers. Please ask factual questions about mutual fund "
        "schemes without sharing personal details."
    ),
    "out_of_scope": (
        "I can only answer factual questions about the five HDFC mutual fund "
        "schemes in our corpus. Please ask about expense ratio, exit load, "
        "minimum SIP, benchmark, or similar scheme facts."
    ),
}


@dataclass(frozen=True)
class AssistantResponse:
    type: str
    text: str
    citation: dict[str, str]
    footer: str
    disclaimer: str
    intent: Intent | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.type,
            "text": self.text,
            "citation": self.citation,
            "footer": self.footer,
            "disclaimer": self.disclaimer,
        }
        if self.intent is not None:
            payload["intent"] = self.intent
        return payload


def _footer(as_of: date | None = None) -> str:
    as_of = as_of or date.today()
    return f"Last updated from sources: {as_of.isoformat()}"


def _citation() -> dict[str, str]:
    settings = get_settings()
    return {
        "url": settings.refusal_citation_url,
        "title": "Mutual Funds on Groww",
    }


def build_refusal(
    intent: Intent,
    *,
    as_of: date | None = None,
) -> AssistantResponse:
    """Build a compliant refusal payload for a non-factual intent."""
    if intent == "factual":
        raise ValueError("Cannot build refusal for factual intent")

    text = _REFUSAL_TEMPLATES.get(intent, _REFUSAL_TEMPLATES["out_of_scope"])
    return AssistantResponse(
        type="refusal",
        text=text,
        citation=_citation(),
        footer=_footer(as_of),
        disclaimer=DISCLAIMER,
        intent=intent,
    )


def classify_and_refuse(
    message: str,
    *,
    use_groq: bool = False,
    as_of: date | None = None,
) -> AssistantResponse | None:
    """Classify a message; return a refusal response when intent is non-factual."""
    result = classify_query(message, use_groq=use_groq)
    if result.intent == "factual":
        return None
    return build_refusal(result.intent, as_of=as_of)


def refusal_from_classification(
    result: ClassificationResult,
    *,
    as_of: date | None = None,
) -> AssistantResponse | None:
    """Build refusal from an existing classification result."""
    if result.intent == "factual":
        return None
    return build_refusal(result.intent, as_of=as_of)
