#!/usr/bin/env python3
"""Inspect vector index embeddings and demo retrieval queries."""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import get_settings  # noqa: E402
from src.retrieval.embedder import Embedder, get_embedder  # noqa: E402
from src.retrieval.retriever import MIN_SCORE, Retriever  # noqa: E402
from src.retrieval.scheme_resolver import resolve_scheme  # noqa: E402
from src.retrieval.section_router import route_section  # noqa: E402
from src.retrieval.vector_store import COLLECTION_NAME, get_chroma_client, get_or_create_collection  # noqa: E402

EXAMPLE_QUERIES: tuple[str, ...] = (
    "What is the expense ratio of HDFC Large Cap Fund Direct Growth?",
    "HDFC Mid Cap minimum SIP amount",
    "exit load on HDFC Gold ETF FoF",
    "ELSS lock-in period HDFC Tax Saver",
    "benchmark for HDFC Small Cap Fund",
    "What is the exit load on HDFC ELSS?",
    "minimum SIP",
    "who is the CEO of Groww",
)

PREVIEW_DIMS = 8


@dataclass(frozen=True)
class IndexedRecord:
    doc_id: str
    text: str
    embedding: list[float]
    metadata: dict


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="View Chroma embeddings and run example retrieval queries.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all indexed chunks with embedding previews (default if no other mode).",
    )
    parser.add_argument(
        "--query",
        metavar="TEXT",
        help="Run a single retrieval query.",
    )
    parser.add_argument(
        "--examples",
        action="store_true",
        help="Run all example queries from the implementation plan.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt for queries interactively until empty input.",
    )
    parser.add_argument(
        "--preview-dims",
        type=int,
        default=PREVIEW_DIMS,
        help=f"Number of embedding dimensions to preview (default: {PREVIEW_DIMS}).",
    )
    return parser.parse_args()


def vector_norm(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values))


def preview_vector(values: list[float], dims: int) -> str:
    head = ", ".join(f"{value:+.4f}" for value in values[:dims])
    suffix = f", ... ({len(values)} dims)" if len(values) > dims else f" ({len(values)} dims)"
    return f"[{head}{suffix}]"


def load_index_records() -> list[IndexedRecord]:
    settings = get_settings()
    client = get_chroma_client(settings)
    collection = get_or_create_collection(client)

    if collection.count() == 0:
        print("Index is empty. Run: python scripts/ingest.py --scheme all --index-only --rebuild", file=sys.stderr)
        sys.exit(1)

    payload = collection.get(include=["embeddings", "documents", "metadatas"])
    records: list[IndexedRecord] = []
    for doc_id, text, embedding, metadata in zip(
        payload["ids"],
        payload["documents"],
        payload["embeddings"],
        payload["metadatas"],
        strict=True,
    ):
        records.append(
            IndexedRecord(
                doc_id=doc_id,
                text=text,
                embedding=embedding,
                metadata=metadata,
            )
        )

    records.sort(key=lambda record: (record.metadata["scheme_id"], record.metadata["page_or_section"]))
    return records


def print_index_summary(records: list[IndexedRecord], embedder: Embedder) -> None:
    settings = get_settings()
    dim = len(records[0].embedding)
    schemes = sorted({record.metadata["scheme_id"] for record in records})
    sections = sorted({record.metadata["page_or_section"] for record in records})

    print("=" * 72)
    print("VECTOR INDEX SUMMARY")
    print("=" * 72)
    print(f"Collection:     {COLLECTION_NAME}")
    print(f"Persist dir:    {settings.chroma_persist_dir}")
    print(f"Embedding model:{embedder.model_name}")
    print(f"Total chunks:   {len(records)}")
    print(f"Vector dims:    {dim}")
    print(f"Schemes:        {len(schemes)}")
    print(f"Sections:       {len(sections)}")
    print(f"Min score:      {MIN_SCORE}")
    print()


def print_embedding_list(records: list[IndexedRecord], preview_dims: int, embedder: Embedder) -> None:
    print_index_summary(records, embedder)
    print("=" * 72)
    print("INDEXED CHUNKS + EMBEDDING PREVIEW")
    print("=" * 72)

    for index, record in enumerate(records, start=1):
        meta = record.metadata
        enriched = embedder.enrich_chunk_text(meta["scheme_name"], meta["page_or_section"], record.text)
        text_preview = record.text.replace("\n", " | ")
        if len(text_preview) > 100:
            text_preview = text_preview[:97] + "..."

        print(f"\n[{index}/{len(records)}] {record.doc_id}")
        print(f"  Scheme:    {meta['scheme_name']}")
        print(f"  Section:   {meta['page_or_section']}")
        print(f"  Date:      {meta['document_date']}")
        print(f"  Norm:      {vector_norm(record.embedding):.4f}")
        print(f"  Embedding: {preview_vector(record.embedding, preview_dims)}")
        print(f"  Embed text:{enriched[:120]}{'...' if len(enriched) > 120 else ''}")
        print(f"  Chunk:     {text_preview}")


def print_retrieval_result(query: str, retriever: Retriever, embedder: Embedder) -> None:
    scheme = resolve_scheme(query)
    section = route_section(query)
    result = retriever.retrieve(query)
    query_vector = embedder.embed_query(query)

    print("=" * 72)
    print(f"QUERY: {query}")
    print("=" * 72)
    print(f"Scheme match:        {scheme.scheme_id or 'none'} ({scheme.confidence})")
    print(f"Section route:       {section.page_or_section or 'none'} ({section.confidence})")
    print(f"Needs disambiguation:{result.needs_disambiguation}")
    print(f"Low confidence:      {result.low_confidence}")
    print(f"Query embedding:     {preview_vector(query_vector, PREVIEW_DIMS)}")
    print()

    if not result.chunks:
        print("No chunks returned.")
        print()
        return

    print("TOP RESULTS")
    print("-" * 72)
    for rank, chunk in enumerate(result.chunks, start=1):
        text_preview = chunk.text.replace("\n", " | ")
        if len(text_preview) > 160:
            text_preview = text_preview[:157] + "..."

        print(f"\n#{rank}  score={chunk.score:.4f}  section={chunk.page_or_section}")
        print(f"    scheme: {chunk.scheme_name}")
        print(f"    url:    {chunk.source_url}")
        print(f"    text:   {text_preview}")

    print()


def run_examples(retriever: Retriever, embedder: Embedder) -> None:
    print("=" * 72)
    print("EXAMPLE RETRIEVAL QUERIES")
    print("=" * 72)
    print()
    for query in EXAMPLE_QUERIES:
        print_retrieval_result(query, retriever, embedder)


def run_interactive(retriever: Retriever, embedder: Embedder) -> None:
    print("Interactive retrieval (empty line to exit).")
    print()
    while True:
        try:
            query = input("Query> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not query:
            break
        print()
        print_retrieval_result(query, retriever, embedder)


def main() -> None:
    args = parse_args()
    embedder = get_embedder()
    retriever = Retriever(embedder=embedder)

    show_list = args.list or not (args.query or args.examples or args.interactive)

    if show_list:
        records = load_index_records()
        print_embedding_list(records, args.preview_dims, embedder)

    if args.query:
        print_retrieval_result(args.query, retriever, embedder)

    if args.examples:
        run_examples(retriever, embedder)

    if args.interactive:
        run_interactive(retriever, embedder)


if __name__ == "__main__":
    main()
