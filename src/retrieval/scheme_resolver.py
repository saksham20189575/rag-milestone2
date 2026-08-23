"""Match user queries to scheme_id via registry keywords and aliases."""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.config.settings import load_schemes

CATEGORY_ALIASES: dict[str, str] = {
    "elss": "hdfc-elss-tax-saver-fund-direct-plan-growth",
    "tax saver": "hdfc-elss-tax-saver-fund-direct-plan-growth",
    "mid cap": "hdfc-mid-cap-fund-direct-growth",
    "midcap": "hdfc-mid-cap-fund-direct-growth",
    "small cap": "hdfc-small-cap-fund-direct-growth",
    "smallcap": "hdfc-small-cap-fund-direct-growth",
    "large cap": "hdfc-large-cap-fund-direct-growth",
    "largecap": "hdfc-large-cap-fund-direct-growth",
    "gold etf": "hdfc-gold-etf-fund-of-fund-direct-plan-growth",
    "gold fof": "hdfc-gold-etf-fund-of-fund-direct-plan-growth",
    "gold fund": "hdfc-gold-etf-fund-of-fund-direct-plan-growth",
}

SCHEME_EXTRA_ALIASES: dict[str, tuple[str, ...]] = {
    "hdfc-elss-tax-saver-fund-direct-plan-growth": ("tax saver", "elss tax saver"),
    "hdfc-gold-etf-fund-of-fund-direct-plan-growth": ("gold etf fof", "gold etf fund of fund"),
}


@dataclass(frozen=True)
class SchemeMatch:
    scheme_id: str | None
    scheme_name: str | None
    confidence: str  # exact | partial | none


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _slug_tokens(scheme_id: str) -> set[str]:
    return {token for token in scheme_id.split("-") if token not in {"hdfc", "fund", "direct", "plan", "growth"}}


def resolve_scheme(query: str, schemes: list[dict] | None = None) -> SchemeMatch:
    """Return the best scheme match for a query."""
    schemes = schemes or load_schemes()
    normalized_query = _normalize(query)

    for scheme in schemes:
        scheme_name = scheme["scheme_name"]
        if _normalize(scheme_name) in normalized_query:
            return SchemeMatch(scheme["scheme_id"], scheme_name, "exact")

    for scheme in schemes:
        scheme_id = scheme["scheme_id"]
        for alias in SCHEME_EXTRA_ALIASES.get(scheme_id, ()):
            if alias in normalized_query:
                return SchemeMatch(scheme_id, scheme["scheme_name"], "partial")

    alias_hits: dict[str, int] = {}
    for alias, scheme_id in CATEGORY_ALIASES.items():
        if alias in normalized_query:
            alias_hits[scheme_id] = alias_hits.get(scheme_id, 0) + 1

    if len(alias_hits) == 1:
        scheme_id = next(iter(alias_hits))
        scheme = next(s for s in schemes if s["scheme_id"] == scheme_id)
        return SchemeMatch(scheme_id, scheme["scheme_name"], "partial")

    partial_scores: list[tuple[int, dict]] = []
    query_tokens = set(re.findall(r"[a-z0-9]+", normalized_query))

    for scheme in schemes:
        scheme_tokens = _slug_tokens(scheme["scheme_id"])
        overlap = len(scheme_tokens & query_tokens)
        name_tokens = set(re.findall(r"[a-z0-9]+", _normalize(scheme["scheme_name"])))
        overlap += len(name_tokens & query_tokens)
        if overlap >= 2:
            partial_scores.append((overlap, scheme))

    if partial_scores:
        partial_scores.sort(key=lambda item: item[0], reverse=True)
        best_score, best_scheme = partial_scores[0]
        if len(partial_scores) == 1 or best_score > partial_scores[1][0]:
            return SchemeMatch(best_scheme["scheme_id"], best_scheme["scheme_name"], "partial")

    return SchemeMatch(None, None, "none")
