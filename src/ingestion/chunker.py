"""Section-aware chunking for processed Groww scheme pages."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

from src.config.settings import PROJECT_ROOT, SCHEMES_PATH, Settings, get_settings, load_schemes
from src.ingestion.parser import (
    DEFAULT_DOC_ID,
    METADATA_SUFFIX,
    normalize_text,
    scheme_processed_dir,
)

CHUNKS_FILENAME = "chunks.jsonl"

TARGET_MIN_TOKENS = 150
TARGET_MAX_TOKENS = 450
HARD_MAX_TOKENS = 600
OVERLAP_TOKENS = 65

FOOTER_MARKERS = ("Home >", "Contact Us", "GROWW")
EXCLUDED_LINE_PREFIXES = (
    "Holdings (",
    "Return calculator",
    "Returns and rankings",
    "Compare similar funds",
    "Understand terms",
)
EXCLUDED_EXACT_LINES = {
    "Fund returns",
    "Check past data",
    "See All",
    "Annualised returns",
    "Absolute returns",
}


@dataclass(frozen=True)
class Chunk:
    text: str
    metadata: dict


@dataclass(frozen=True)
class ChunkResult:
    scheme_id: str
    chunks_path: Path
    chunk_count: int
    ingested_at: str


class ChunkError(Exception):
    """Raised when chunking fails."""


def estimate_tokens(text: str) -> int:
    """Rough token count (~4 characters or ~1.3 words per token)."""
    words = len(text.split())
    return max(1, int(max(len(text) / 4, words * 1.3)))


def content_hash(text: str) -> str:
    digest = hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def load_amc() -> str:
    with open(SCHEMES_PATH, encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data.get("amc", "HDFC Mutual Fund")


def _trim_leading_chrome(lines: list[str], scheme_name: str) -> list[str]:
    for index, line in enumerate(lines):
        if line.strip() == scheme_name.strip():
            return lines[index:]
    return lines


def _trim_trailing_chrome(lines: list[str]) -> list[str]:
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped in FOOTER_MARKERS or stripped.startswith("Home >"):
            return lines[:index]
    return lines


def cleanup_lines(lines: list[str], scheme_name: str) -> list[str]:
    cleaned = _trim_leading_chrome(lines, scheme_name)
    cleaned = _trim_trailing_chrome(cleaned)
    return [line.rstrip() for line in cleaned]


def _find_line(lines: list[str], target: str, *, start: int = 0, end: int | None = None) -> int | None:
    end = len(lines) if end is None else end
    for index in range(start, end):
        if lines[index].strip() == target:
            return index
    return None


def _find_line_contains(lines: list[str], needle: str, *, start: int = 0, end: int | None = None) -> int | None:
    end = len(lines) if end is None else end
    for index in range(start, end):
        if needle in lines[index]:
            return index
    return None


def _find_line_prefix(lines: list[str], prefix: str, *, start: int = 0, end: int | None = None) -> int | None:
    end = len(lines) if end is None else end
    for index in range(start, end):
        if lines[index].strip().startswith(prefix):
            return index
    return None


def _lines_to_text(lines: list[str]) -> str:
    return normalize_text("\n".join(line for line in lines if line is not None))


def _is_excluded_boundary(line: str) -> bool:
    stripped = line.strip()
    if stripped in EXCLUDED_EXACT_LINES:
        return True
    return any(stripped.startswith(prefix) for prefix in EXCLUDED_LINE_PREFIXES)


def _extract_range(lines: list[str], start: int, end: int) -> list[str]:
    block = lines[start:end]
    trimmed: list[str] = []
    for line in block:
        if _is_excluded_boundary(line):
            break
        trimmed.append(line)
    return trimmed


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _split_with_overlap(
    text: str,
    *,
    section_name: str,
    scheme_name: str,
    max_tokens: int = HARD_MAX_TOKENS,
    overlap_tokens: int = OVERLAP_TOKENS,
) -> list[str]:
    if estimate_tokens(text) <= max_tokens:
        return [text]

    prefix = f"{scheme_name}\n{section_name}\n"
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[str] = []
    current = prefix

    def flush() -> None:
        nonlocal current
        body = current[len(prefix) :] if current.startswith(prefix) else current
        if body.strip():
            chunks.append(normalize_text(current))
        current = prefix

    for paragraph in paragraphs:
        candidate = normalize_text(f"{current}\n{paragraph}" if current.strip() else paragraph)
        if estimate_tokens(candidate) <= max_tokens:
            current = candidate
            continue
        flush()
        if estimate_tokens(paragraph) <= max_tokens:
            current = normalize_text(f"{prefix}{paragraph}")
            continue
        for sentence in _split_sentences(paragraph):
            candidate = normalize_text(f"{current}\n{sentence}" if current.strip() else f"{prefix}{sentence}")
            if estimate_tokens(candidate) <= max_tokens:
                current = candidate
            else:
                flush()
                current = normalize_text(f"{prefix}{sentence}")

    flush()

    if len(chunks) <= 1:
        return chunks or [text]

    overlapped: list[str] = [chunks[0]]
    for chunk in chunks[1:]:
        prior = overlapped[-1]
        prior_tail = " ".join(prior.split()[-overlap_tokens:])
        merged = normalize_text(f"{prior_tail}\n{chunk}")
        overlapped.append(merged)
    return overlapped


def _section_specs(scheme_name: str) -> list[tuple[str, str]]:
    return [
        ("Fund overview", scheme_name),
        ("ELSS lock-in", "Lock-in"),
        ("Minimum investments", "Minimum investments"),
        ("Exit load, stamp duty and tax", "Exit load, stamp duty and tax"),
        ("About the fund", f"About {scheme_name}"),
        ("Investment objective and benchmark", "Investment Objective"),
        ("Fund house", "Fund house"),
    ]


def extract_sections(lines: list[str], scheme: dict) -> list[tuple[str, str]]:
    scheme_name = scheme["scheme_name"]
    specs = _section_specs(scheme_name)
    starts: list[tuple[str, int]] = []

    for section_name, marker in specs:
        if section_name == "ELSS lock-in" and scheme.get("category") != "ELSS":
            continue
        if section_name == "ELSS lock-in":
            index = _find_line_contains(lines, "Lock-in", start=0, end=min(len(lines), 120))
        elif section_name == "Fund overview":
            index = _find_line(lines, scheme_name)
        else:
            index = _find_line(lines, marker)
        if index is not None:
            starts.append((section_name, index))

    starts.sort(key=lambda item: item[1])
    sections: list[tuple[str, str]] = []

    for idx, (section_name, start) in enumerate(starts):
        next_start = starts[idx + 1][1] if idx + 1 < len(starts) else len(lines)
        end = next_start

        if section_name == "Fund overview":
            return_calc = _find_line(lines, "Return calculator", start=start)
            holdings = _find_line_prefix(lines, "Holdings (", start=start)
            stops = [pos for pos in (return_calc, holdings) if pos is not None]
            if stops:
                end = min(stops)
            elif next_start < len(lines) and starts[idx + 1][0] == "ELSS lock-in":
                # Keep hero facts through to Return calculator / Holdings, not ELSS lock-in marker.
                end = len(lines)
        elif section_name == "Minimum investments":
            stop = _find_line(lines, "Understand terms", start=start, end=end)
            if stop is not None:
                end = stop
        elif section_name == "Exit load, stamp duty and tax":
            stop = _find_line(lines, "Compare similar funds", start=start, end=end)
            if stop is None:
                stop = _find_line(lines, "Check past data", start=start, end=end)
            if stop is not None:
                end = stop
        elif section_name == "ELSS lock-in":
            end = min(end, start + 3)

        block_lines = _extract_range(lines, start, end)
        text = _lines_to_text(block_lines)
        if text:
            sections.append((section_name, text))

    return sections


def build_chunk_metadata(
    *,
    scheme: dict,
    parse_meta: dict,
    page_or_section: str,
    text: str,
    ingested_at: str,
    amc: str,
) -> dict:
    return {
        "scheme_id": scheme["scheme_id"],
        "scheme_name": scheme["scheme_name"],
        "category": scheme.get("category"),
        "amc": amc,
        "document_type": parse_meta.get("document_type", "groww_scheme_page"),
        "source_url": parse_meta.get("source_url", scheme["source_url"]),
        "source_domain": parse_meta.get("source_domain", "groww.in"),
        "page_or_section": page_or_section,
        "content_hash": content_hash(text),
        "document_date": parse_meta.get("document_date"),
        "ingested_at": ingested_at,
    }


def chunk_text(lines: list[str], scheme: dict, *, ingested_at: str, amc: str, parse_meta: dict) -> list[Chunk]:
    cleaned = cleanup_lines(lines, scheme["scheme_name"])
    sections = extract_sections(cleaned, scheme)

    chunks: list[Chunk] = []
    seen_hashes: set[str] = set()

    for section_name, section_text in sections:
        for piece in _split_with_overlap(
            section_text,
            section_name=section_name,
            scheme_name=scheme["scheme_name"],
        ):
            metadata = build_chunk_metadata(
                scheme=scheme,
                parse_meta=parse_meta,
                page_or_section=section_name,
                text=piece,
                ingested_at=ingested_at,
                amc=amc,
            )
            digest = metadata["content_hash"]
            if digest in seen_hashes:
                continue
            seen_hashes.add(digest)
            chunks.append(Chunk(text=piece, metadata=metadata))

    if not chunks:
        raise ChunkError(f"No chunks produced for scheme: {scheme['scheme_id']}")
    return chunks


def chunk_document(
    scheme: dict,
    *,
    settings: Settings | None = None,
    doc_id: str = DEFAULT_DOC_ID,
) -> ChunkResult:
    settings = settings or get_settings()
    scheme_id = scheme["scheme_id"]
    processed_dir = scheme_processed_dir(scheme_id, settings)
    text_path = processed_dir / f"{doc_id}.txt"
    metadata_path = processed_dir / f"{doc_id}{METADATA_SUFFIX}"

    if not text_path.exists() or not metadata_path.exists():
        raise ChunkError(f"Missing processed document for scheme: {scheme_id}")

    lines = text_path.read_text(encoding="utf-8").splitlines()
    parse_meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    ingested_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    amc = load_amc()

    chunks = chunk_text(lines, scheme, ingested_at=ingested_at, amc=amc, parse_meta=parse_meta)
    chunks_path = processed_dir / CHUNKS_FILENAME
    with chunks_path.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps({"text": chunk.text, "metadata": chunk.metadata}, ensure_ascii=False) + "\n")

    return ChunkResult(
        scheme_id=scheme_id,
        chunks_path=chunks_path,
        chunk_count=len(chunks),
        ingested_at=ingested_at,
    )


def chunk_schemes(
    schemes: list[dict] | None = None,
    *,
    scheme_ids: set[str] | None = None,
    settings: Settings | None = None,
) -> list[ChunkResult]:
    all_schemes = schemes or load_schemes()
    if scheme_ids is not None:
        all_schemes = [scheme for scheme in all_schemes if scheme["scheme_id"] in scheme_ids]
    return [chunk_document(scheme, settings=settings) for scheme in all_schemes]


def load_chunks(scheme_id: str, settings: Settings | None = None) -> list[Chunk]:
    settings = settings or get_settings()
    chunks_path = scheme_processed_dir(scheme_id, settings) / CHUNKS_FILENAME
    if not chunks_path.exists():
        raise ChunkError(f"No chunks found for scheme: {scheme_id}")

    chunks: list[Chunk] = []
    for line in chunks_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        chunks.append(Chunk(text=payload["text"], metadata=payload["metadata"]))
    return chunks


def chunk_result_to_dict(result: ChunkResult) -> dict:
    data = asdict(result)
    data["chunks_path"] = str(result.chunks_path.relative_to(PROJECT_ROOT))
    return data
