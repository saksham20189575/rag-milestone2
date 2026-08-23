#!/usr/bin/env python3
"""CLI for corpus ingestion (fetch → parse → chunk → embed → index)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import load_schemes  # noqa: E402
from src.ingestion.fetcher import FetchError, fetch_schemes  # noqa: E402
from src.ingestion.indexer import IndexError, collection_count, index_chunks  # noqa: E402
from src.ingestion.parser import ParseError, parse_result_to_dict, parse_schemes  # noqa: E402
from src.ingestion.chunker import ChunkError, chunk_result_to_dict, chunk_schemes  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest Groww scheme pages into the vector index.",
    )
    parser.add_argument(
        "--scheme",
        required=True,
        help='Scheme ID to ingest, or "all" for every scheme in the registry.',
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Drop existing index data before re-ingesting.",
    )
    parser.add_argument(
        "--index-only",
        action="store_true",
        help="Skip fetch/parse/chunk; embed and index existing chunks.jsonl files.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Replace indexed chunks for the target scheme(s) before upserting.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    schemes = load_schemes()
    scheme_ids = {s["scheme_id"] for s in schemes}

    if args.scheme != "all" and args.scheme not in scheme_ids:
        print(f"Unknown scheme: {args.scheme}", file=sys.stderr)
        print(f"Available: {', '.join(sorted(scheme_ids))}, all", file=sys.stderr)
        sys.exit(1)

    scheme_filter = None if args.scheme == "all" else {args.scheme}

    try:
        if not args.index_only:
            fetch_schemes(scheme_ids=scheme_filter)
            parse_results = parse_schemes(scheme_ids=scheme_filter)
            chunk_results = chunk_schemes(scheme_ids=scheme_filter)
        else:
            parse_results = []
            chunk_results = []

        index_result = index_chunks(
            scheme_ids=scheme_filter,
            rebuild=args.rebuild,
            refresh=args.refresh,
        )
    except (FetchError, ParseError, ChunkError, IndexError) as exc:
        print(f"Ingest failed: {exc}", file=sys.stderr)
        sys.exit(1)

    for result in parse_results:
        summary = parse_result_to_dict(result)
        print(
            f"Parsed {summary['scheme_id']} → {summary['text_path']} "
            f"({summary['char_count']} chars, date={summary['document_date']}, "
            f"method={summary['parse_method']})"
        )

    for result in chunk_results:
        summary = chunk_result_to_dict(result)
        print(
            f"Chunked {summary['scheme_id']} → {summary['chunks_path']} "
            f"({summary['chunk_count']} chunks)"
        )

    print(
        f"Indexed {index_result.indexed_count} new chunks "
        f"({index_result.skipped_count} skipped, total in store={collection_count()})"
    )


if __name__ == "__main__":
    main()
