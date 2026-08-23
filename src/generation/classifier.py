"""Query intent classification — rule-based with optional Groq fallback."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from src.config.settings import get_settings
from src.generation.groq_client import GroqClient
from src.retrieval.scheme_resolver import resolve_scheme

Intent = Literal["factual", "advisory", "comparative", "performance", "pii", "out_of_scope"]

# Indian PAN: 5 letters + 4 digits + 1 letter
_PAN_PATTERN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b", re.IGNORECASE)
# Aadhaar: 12 digits, optionally grouped as 4-4-4
_AADHAAR_PATTERN = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_PATTERN = re.compile(r"\b(?:\+91[\s-]?)?[6-9]\d{9}\b")

_RULE_PATTERNS: tuple[tuple[Intent, re.Pattern[str]], ...] = (
    (
        "advisory",
        re.compile(
            r"(?:"
            r"should\s+i\s+(?:invest|buy|sell|redeem|switch|put|allocate)"
            r"|(?:do|would|can)\s+you\s+recommend"
            r"|(?:is|are)\s+(?:this|it|that)\s+(?:fund|scheme)\s+good"
            r"|(?:is|are)\s+(?:this|it)\s+a\s+good\s+(?:fund|investment)"
            r"|worth\s+investing"
            r"|buy\s+or\s+sell"
            r"|(?:good|bad)\s+(?:idea|choice)\s+to\s+invest"
            r"|(?:advise|advice)\s+(?:me\s+on\s+)?(?:invest(?:ing)?|buy(?:ing)?|sell(?:ing)?|fund|scheme)"
            r"|(?:is|are)\s+.+\s+a\s+good\s+investment"
            r"|tell\s+me\s+if\s+i\s+should\s+invest"
            r"|(?:would|should)\s+(?:you|i)\s+(?:invest|buy|sell|redeem)"
            r")",
            re.IGNORECASE,
        ),
    ),
    (
        "comparative",
        re.compile(
            r"(?:"
            r"which\s+fund\s+is\s+better"
            r"|(?:better|best|worst)\s+fund"
            r"|(?:best|top|worst)\s+(?:\w+\s+){0,4}(?:mutual\s+)?fund"
            r"|\bfund\b.*\b(?:better|best|worst)\b"
            r"|\bcompare\b"
            r"|\bvs\.?\b"
            r"|\bversus\b"
            r"|which\s+(?:one|fund|scheme)\s+(?:is|should)"
            r")",
            re.IGNORECASE,
        ),
    ),
    (
        "performance",
        re.compile(
            r"(?:"
            r"returns?\s+if\s+i"
            r"|\bcagr\b"
            r"|how\s+much\s+will\s+i\s+(?:earn|make|get)"
            r"|\bhow\s+much\s+(?:money|return)"
            r"|\bpredict\b"
            r"|if\s+i\s+invest\s+\d"
            r"|will\s+i\s+(?:earn|make|get)\s+(?:if|from)"
            r"|(?:calculate|compute)\s+(?:my\s+)?returns?"
            r"|how\s+much\s+(?:would|will)\s+(?:it|i)\s+(?:grow|be\s+worth)"
            r")",
            re.IGNORECASE,
        ),
    ),
)

_FUND_KEYWORDS = re.compile(
    r"(?:"
    r"mutual\s+fund|scheme|expense\s+ratio|exit\s+load|"
    r"\bsip\b|elss|benchmark|\bnav\b|\baum\b|riskometer|"
    r"lock[\s-]?in|redemption|stamp\s+duty|fund\s+house|"
    r"\bamc\b|\bhdfc\b|minimum\s+investment|"
    r"lumpsum|tax\s+saver|mid\s+cap|small\s+cap|large\s+cap|"
    r"gold\s+etf|investment\s+objective|registrar|custodian|"
    r"fund\s+manager|direct\s+(?:plan|growth)|risk\s+label|"
    r"fund\s+size|fund\s+benchmark"
    r")",
    re.IGNORECASE,
)

_GROQ_SYSTEM_PROMPT = """You classify user messages for a facts-only mutual fund FAQ assistant.

Reply with exactly one label (lowercase, no punctuation):
- factual — objective questions about scheme facts (expense ratio, exit load, SIP minimum, benchmark, lock-in, NAV, etc.)
- advisory — investment advice, recommendations, whether to buy/sell/invest
- comparative — comparing funds or asking which is better/best
- performance — personal return calculations, predictions, or CAGR forecasts
- pii — contains personal identifiable information (PAN, Aadhaar, email, phone, account numbers)
- out_of_scope — unrelated to mutual fund scheme facts

Reply with only the label."""

_VALID_GROQ_LABELS = frozenset({"factual", "advisory", "comparative", "performance", "pii", "out_of_scope"})


@dataclass(frozen=True)
class ClassificationResult:
    intent: Intent
    method: str  # rule | groq | heuristic
    matched_pattern: str | None = None


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _detect_pii(query: str) -> bool:
    return bool(
        _PAN_PATTERN.search(query)
        or _AADHAAR_PATTERN.search(query)
        or _EMAIL_PATTERN.search(query)
        or _PHONE_PATTERN.search(query)
    )


def contains_pii(query: str) -> bool:
    """Return True when the query contains PII patterns."""
    return _detect_pii(_normalize(query))


_SCHEME_SIGNAL = re.compile(
    r"\bhdfc\b|elss|mid[\s-]?cap|small[\s-]?cap|large[\s-]?cap|gold|tax\s+saver",
    re.IGNORECASE,
)


def _is_fund_related(query: str) -> bool:
    if _FUND_KEYWORDS.search(query):
        return True
    match = resolve_scheme(query)
    if match.confidence == "exact":
        return True
    if match.confidence == "partial" and _SCHEME_SIGNAL.search(query):
        return True
    return False


def _classify_with_rules(query: str) -> ClassificationResult | None:
    if _detect_pii(query):
        return ClassificationResult("pii", "rule", "pii_pattern")

    for intent, pattern in _RULE_PATTERNS:
        match = pattern.search(query)
        if match:
            return ClassificationResult(intent, "rule", match.group(0))

    return None


def _classify_with_groq(query: str, groq_client: GroqClient | None = None) -> ClassificationResult:
    client = groq_client or GroqClient()
    settings = get_settings()
    label = client.chat(
        system=_GROQ_SYSTEM_PROMPT,
        user=query,
        model=settings.groq_model_fast,
        temperature=0.0,
        max_tokens=16,
    ).strip().lower()

    for valid in _VALID_GROQ_LABELS:
        if valid in label:
            return ClassificationResult(valid, "groq", label)

    return ClassificationResult("out_of_scope", "groq", label)


def classify_query(
    query: str,
    *,
    use_groq: bool = False,
    groq_client: GroqClient | None = None,
) -> ClassificationResult:
    """Classify user query intent before retrieval."""
    normalized = _normalize(query)
    if not normalized:
        return ClassificationResult("out_of_scope", "heuristic", "empty_query")

    rule_result = _classify_with_rules(normalized)
    if rule_result is not None:
        return rule_result

    if _is_fund_related(normalized):
        return ClassificationResult("factual", "heuristic", "fund_related")

    if use_groq and get_settings().groq_api_key:
        return _classify_with_groq(normalized, groq_client)

    return ClassificationResult("out_of_scope", "heuristic", "not_fund_related")


def is_factual(query: str, **kwargs: object) -> bool:
    """Return True when the query should proceed to the RAG pipeline."""
    return classify_query(query, **kwargs).intent == "factual"
