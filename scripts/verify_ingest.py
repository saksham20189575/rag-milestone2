#!/usr/bin/env python3
"""Post-ingest verification for CI and manual checks."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import get_settings, load_schemes  # noqa: E402
from src.ingestion.chunker import load_chunks  # noqa: E402
from src.ingestion.indexer import collection_count  # noqa: E402

MIN_CHROMA_CHUNKS = 31
TEXT_FILENAME = "groww_scheme_page.txt"


def main() -> None:
    settings = get_settings()
    schemes = load_schemes()
    errors: list[str] = []
    total_chunks = 0
    max_document_date: str | None = None

    print("Ingest verification summary")
    print("-" * 40)

    for scheme in schemes:
        scheme_id = scheme["scheme_id"]
        text_path = settings.processed_data_dir / scheme_id / TEXT_FILENAME
        if not text_path.exists():
            errors.append(f"{scheme_id}: missing processed text at {text_path}")
            continue
        if text_path.stat().st_size == 0:
            errors.append(f"{scheme_id}: empty processed text at {text_path}")

        chunks = load_chunks(scheme_id, settings=settings)
        chunk_count = len(chunks)
        total_chunks += chunk_count
        min_expected = 7 if "elss" in scheme_id else 6
        if chunk_count < min_expected:
            errors.append(
                f"{scheme_id}: expected >={min_expected} chunks, got {chunk_count}"
            )

        for chunk in chunks:
            document_date = chunk.metadata.get("document_date")
            if document_date and (
                max_document_date is None or document_date > max_document_date
            ):
                max_document_date = document_date

        print(f"  {scheme_id}: {chunk_count} chunks")

    chroma_count = collection_count(settings)
    print(f"Chroma collection count: {chroma_count}")
    print(f"Total chunks.jsonl records: {total_chunks}")
    if max_document_date:
        print(f"Latest document_date: {max_document_date}")

    if chroma_count < MIN_CHROMA_CHUNKS:
        errors.append(
            f"Chroma count {chroma_count} is below minimum {MIN_CHROMA_CHUNKS}"
        )

    if errors:
        print("-" * 40)
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)

    print("-" * 40)
    print("Ingest verification passed.")


if __name__ == "__main__":
    main()
