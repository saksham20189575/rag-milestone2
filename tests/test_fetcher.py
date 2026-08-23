import pytest

from src.config.settings import REFUSAL_CITATION_URL
from src.ingestion.fetcher import FetchError, is_allowed_domain, validate_source_url


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth", True),
        ("https://www.groww.in/mutual-funds/foo", True),
        ("https://groww.in/p/mutual-funds", True),
        ("https://amfiindia.com/scheme", False),
        ("http://groww.in/mutual-funds/foo", True),
        ("https://evil-groww.in/mutual-funds/foo", False),
    ],
)
def test_is_allowed_domain(url: str, expected: bool) -> None:
    assert is_allowed_domain(url) is expected


def test_validate_source_url_rejects_non_https() -> None:
    with pytest.raises(FetchError, match="HTTPS"):
        validate_source_url("http://groww.in/mutual-funds/foo")


def test_validate_source_url_rejects_non_allowlisted_domain() -> None:
    with pytest.raises(FetchError, match="allowlisted"):
        validate_source_url("https://example.com/mutual-funds/foo")


def test_refusal_citation_url_not_used_as_corpus_source() -> None:
    assert REFUSAL_CITATION_URL == "https://groww.in/p/mutual-funds"
    assert is_allowed_domain(REFUSAL_CITATION_URL)
