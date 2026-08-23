"""Parse Groww scheme HTML into normalized plain text."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import trafilatura
from bs4 import BeautifulSoup, NavigableString, Tag

from src.config.settings import PROJECT_ROOT, Settings, get_settings, load_schemes
from src.ingestion.fetcher import HTML_FILENAME, load_fetch_metadata, scheme_output_dir

DEFAULT_DOC_ID = "groww_scheme_page"
METADATA_SUFFIX = ".meta.json"
MIN_TEXT_LENGTH = 500

HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
BLOCK_TAGS = {"p", "li", "td", "th", "dt", "dd", "blockquote"}

NAV_DATE_PATTERNS = (
    re.compile(r"NAV(?: of [^<\n]+)? is [^\n<]+ as of (\d{1,2}\s+\w+\s+\d{4})", re.I),
    re.compile(r"NAV as of (\d{1,2}\s+\w+\s+\d{4})", re.I),
    re.compile(r"as of (\d{1,2}\s+\w+\s+\d{4})", re.I),
)
ISO_DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")
HUMAN_DATE_FORMATS = ("%d %b %Y", "%d %B %Y", "%d %b %y")


@dataclass(frozen=True)
class ParseResult:
    scheme_id: str
    doc_id: str
    text_path: Path
    metadata_path: Path
    document_date: str | None
    parsed_at: str
    char_count: int
    parse_method: str


class ParseError(Exception):
    """Raised when HTML cannot be parsed into usable text."""


def scheme_processed_dir(scheme_id: str, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return settings.processed_data_dir / scheme_id


def normalize_text(text: str) -> str:
    """Normalize unicode and collapse excessive whitespace."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.strip() for line in text.splitlines()]

    normalized_lines: list[str] = []
    previous_blank = False
    for line in lines:
        if not line:
            if normalized_lines and not previous_blank:
                normalized_lines.append("")
            previous_blank = True
            continue
        normalized_lines.append(line)
        previous_blank = False
    return "\n".join(normalized_lines).strip()


def _parse_human_date(raw: str) -> str | None:
    cleaned = re.sub(r"\s+", " ", raw.strip())
    for fmt in HUMAN_DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def extract_document_date(html: str, fallback: str | None = None) -> str | None:
    """Extract NAV / page date from HTML, falling back to fetch timestamp date."""
    for pattern in NAV_DATE_PATTERNS:
        match = pattern.search(html)
        if match:
            parsed = _parse_human_date(match.group(1))
            if parsed:
                return parsed

    for script_match in re.finditer(
        r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        re.S | re.I,
    ):
        try:
            payload = json.loads(script_match.group(1))
        except json.JSONDecodeError:
            continue
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            for key in ("dateModified", "datePublished", "uploadDate"):
                value = item.get(key)
                if isinstance(value, str):
                    iso_match = ISO_DATE_PATTERN.search(value)
                    if iso_match:
                        return iso_match.group(1)

    json_date = re.search(
        r'"(?:dateModified|datePublished|uploadDate)"\s*:\s*"(\d{4}-\d{2}-\d{2})',
        html,
        re.I,
    )
    if json_date:
        return json_date.group(1)

    if fallback:
        if fallback.endswith("Z"):
            fallback = fallback[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(fallback).date().isoformat()
        except ValueError:
            iso_match = ISO_DATE_PATTERN.search(fallback)
            if iso_match:
                return iso_match.group(1)
    return None


def _element_to_text(element: Tag) -> str:
    parts: list[str] = []

    def walk(node: Tag | NavigableString) -> None:
        if isinstance(node, NavigableString):
            text = str(node).strip()
            if text:
                parts.append(text)
            return

        if node.name in HEADING_TAGS:
            heading = node.get_text(" ", strip=True)
            if heading:
                parts.extend(["", heading, ""])
            return

        if node.name in BLOCK_TAGS:
            block = node.get_text(" ", strip=True)
            if block:
                parts.append(block)
            return

        for child in node.children:
            if isinstance(child, (Tag, NavigableString)):
                walk(child)

    walk(element)
    return normalize_text("\n".join(parts))


def _extract_with_beautifulsoup(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    main = soup.find("main") or soup.body or soup
    return _element_to_text(main)


def _extract_with_trafilatura(html: str) -> str:
    extracted = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        include_links=False,
    )
    return normalize_text(extracted or "")


def _merge_extractions(*chunks: str) -> str:
    seen: set[str] = set()
    merged: list[str] = []
    for chunk in chunks:
        chunk = normalize_text(chunk)
        if not chunk or chunk in seen:
            continue
        seen.add(chunk)
        merged.append(chunk)
    return normalize_text("\n\n".join(merged))


def _fetch_rendered_html(source_url: str) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ParseError("Playwright is required for JS-rendered pages") from exc

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(source_url, wait_until="networkidle", timeout=60_000)
            html = page.content()
            browser.close()
    except Exception as exc:
        raise ParseError(f"Playwright render failed for {source_url}: {exc}") from exc
    return html


def _trim_leading_chrome(text: str, scheme_name: str | None = None) -> str:
    """Drop Groww global navigation that precedes the scheme heading."""
    if not scheme_name:
        return text
    marker = scheme_name.strip()
    idx = text.find(marker)
    if idx > 0:
        return text[idx:].strip()
    return text


def parse_html(
    html: str,
    *,
    source_url: str | None = None,
    fallback_date: str | None = None,
    allow_playwright: bool = True,
) -> tuple[str, str | None, str]:
    """Parse HTML to normalized text, returning (text, document_date, method)."""
    text = _merge_extractions(_extract_with_beautifulsoup(html), _extract_with_trafilatura(html))
    method = "beautifulsoup+trafilatura"

    if len(text) < MIN_TEXT_LENGTH:
        if not allow_playwright or not source_url:
            raise ParseError("Extracted text is empty or too short")
        html = _fetch_rendered_html(source_url)
        text = _merge_extractions(_extract_with_beautifulsoup(html), _extract_with_trafilatura(html))
        method = "playwright+beautifulsoup+trafilatura"
        if len(text) < MIN_TEXT_LENGTH:
            raise ParseError("Rendered page still produced insufficient text")

    document_date = extract_document_date(html, fallback=fallback_date)
    return normalize_text(text), document_date, method


def parse_scheme_page(
    scheme: dict,
    *,
    settings: Settings | None = None,
    doc_id: str = DEFAULT_DOC_ID,
    allow_playwright: bool = True,
) -> ParseResult:
    """Parse one fetched Groww page and write normalized text to data/processed/."""
    settings = settings or get_settings()
    scheme_id = scheme["scheme_id"]
    fetch_meta = load_fetch_metadata(scheme_id, settings)
    html_path = scheme_output_dir(scheme_id, settings) / HTML_FILENAME
    if not html_path.exists():
        raise ParseError(f"Missing raw HTML for scheme: {scheme_id}")

    html = html_path.read_text(encoding="utf-8")
    text, document_date, method = parse_html(
        html,
        source_url=scheme["source_url"],
        fallback_date=fetch_meta.get("fetched_at"),
        allow_playwright=allow_playwright,
    )
    text = _trim_leading_chrome(text, scheme.get("scheme_name"))

    out_dir = scheme_processed_dir(scheme_id, settings)
    out_dir.mkdir(parents=True, exist_ok=True)
    text_path = out_dir / f"{doc_id}.txt"
    metadata_path = out_dir / f"{doc_id}{METADATA_SUFFIX}"
    parsed_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    text_path.write_text(text + "\n", encoding="utf-8")
    metadata = {
        "scheme_id": scheme_id,
        "scheme_name": scheme["scheme_name"],
        "category": scheme.get("category"),
        "doc_id": doc_id,
        "document_type": "groww_scheme_page",
        "source_url": scheme["source_url"],
        "source_domain": fetch_meta.get("source_domain", "groww.in"),
        "document_date": document_date,
        "parsed_at": parsed_at,
        "fetched_at": fetch_meta.get("fetched_at"),
        "parse_method": method,
        "char_count": len(text),
        "raw_html_path": str(html_path.relative_to(PROJECT_ROOT)),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    return ParseResult(
        scheme_id=scheme_id,
        doc_id=doc_id,
        text_path=text_path,
        metadata_path=metadata_path,
        document_date=document_date,
        parsed_at=parsed_at,
        char_count=len(text),
        parse_method=method,
    )


def parse_schemes(
    schemes: list[dict] | None = None,
    *,
    scheme_ids: set[str] | None = None,
    settings: Settings | None = None,
    allow_playwright: bool = True,
) -> list[ParseResult]:
    """Parse fetched pages for all or selected schemes."""
    all_schemes = schemes or load_schemes()
    if scheme_ids is not None:
        all_schemes = [s for s in all_schemes if s["scheme_id"] in scheme_ids]
    return [
        parse_scheme_page(scheme, settings=settings, allow_playwright=allow_playwright)
        for scheme in all_schemes
    ]


def load_parse_metadata(scheme_id: str, doc_id: str = DEFAULT_DOC_ID, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    metadata_path = scheme_processed_dir(scheme_id, settings) / f"{doc_id}{METADATA_SUFFIX}"
    if not metadata_path.exists():
        raise ParseError(f"No parse metadata found for scheme: {scheme_id}")
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def parse_result_to_dict(result: ParseResult) -> dict:
    data = asdict(result)
    data["text_path"] = str(result.text_path.relative_to(PROJECT_ROOT))
    data["metadata_path"] = str(result.metadata_path.relative_to(PROJECT_ROOT))
    return data
