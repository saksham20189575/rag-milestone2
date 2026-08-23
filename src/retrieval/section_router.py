"""Map query keywords to page_or_section for retrieval routing."""

from __future__ import annotations

import re
from dataclasses import dataclass

FUND_HOUSE_SECTION = "Fund house"
ABOUT_SECTION = "About the fund"

SECTION_RULES: tuple[tuple[str, tuple[str, ...], bool], ...] = (
    (
        "Fund overview",
        (
            r"expense ratio",
            r"\bnav\b",
            r"\baum\b",
            r"fund size",
            r"riskometer",
            r"\brating\b",
            r"\brisk\b",
        ),
        True,
    ),
    (
        "Minimum investments",
        (
            r"minimum sip",
            r"min\.?\s*sip",
            r"\blumpsum\b",
            r"first investment",
            r"minimum investment",
        ),
        True,
    ),
    (
        "Exit load, stamp duty and tax",
        (
            r"exit load",
            r"redemption",
            r"stamp duty",
            r"tax implication",
            r"\bredeem\b",
        ),
        True,
    ),
    (
        "Investment objective and benchmark",
        (
            r"benchmark",
            r"\bindex\b",
            r"investment objective",
            r"\bsid\b",
        ),
        True,
    ),
    (
        "ELSS lock-in",
        (
            r"lock-?in",
            r"elss period",
            r"3\s*year",
        ),
        True,
    ),
    (
        ABOUT_SECTION,
        (
            r"fund manager",
            r"\babout\b",
            r"launch date",
        ),
        False,
    ),
    (
        FUND_HOUSE_SECTION,
        (
            r"\bamc\b",
            r"registrar",
            r"custodian",
            r"fund house",
        ),
        False,
    ),
)


@dataclass(frozen=True)
class SectionRoute:
    page_or_section: str | None
    confidence: str  # high | low | none
    is_faq_fact: bool


def route_section(query: str) -> SectionRoute:
    """Return the best matching section for a query."""
    normalized = query.lower()

    for section, patterns, is_faq_fact in SECTION_RULES:
        for pattern in patterns:
            if re.search(pattern, normalized):
                return SectionRoute(section, "high", is_faq_fact)

    if re.search(r"objective", normalized):
        return SectionRoute(ABOUT_SECTION, "low", False)

    return SectionRoute(None, "none", False)
