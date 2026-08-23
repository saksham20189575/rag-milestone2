"""Load chunks into Chroma with deduplication by scheme_id + content_hash."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from src.config.settings import Settings, get_settings, load_schemes
from src.ingestion.chunker import Chunk, load_chunks
from src.retrieval.embedder import Embedder, get_embedder
from src.retrieval.vector_store import COLLECTION_NAME, get_chroma_client, get_or_create_collection


class IndexError(Exception):
    """Raised when indexing fails."""


@dataclass(frozen=True)
class IndexResult:
    indexed_count: int
    skipped_count: int
    collection_name: str
    persist_dir: Path


def chunk_id(scheme_id: str, content_hash: str) -> str:
    return f"{scheme_id}:{content_hash}"


def load_all_chunks(
    scheme_ids: set[str] | None = None,
    settings: Settings | None = None,
) -> list[Chunk]:
    settings = settings or get_settings()
    schemes = load_schemes()
    if scheme_ids is not None:
        schemes = [scheme for scheme in schemes if scheme["scheme_id"] in scheme_ids]

    chunks: list[Chunk] = []
    for scheme in schemes:
        chunks.extend(load_chunks(scheme["scheme_id"], settings=settings))
    return chunks


def rebuild_index(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if settings.chroma_persist_dir.exists():
        shutil.rmtree(settings.chroma_persist_dir)
    settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)


def delete_scheme_chunks(collection, scheme_id: str) -> int:
    """Remove all indexed chunks for a scheme (used before daily refresh)."""
    result = collection.get(where={"scheme_id": scheme_id}, include=[])
    ids = result.get("ids") or []
    if ids:
        collection.delete(ids=ids)
    return len(ids)


def refresh_scheme_chunks(
    collection,
    scheme_ids: set[str] | None = None,
    settings: Settings | None = None,
) -> int:
    """Delete indexed chunks for the given schemes so they can be re-upserted."""
    settings = settings or get_settings()
    schemes = load_schemes()
    targets = {scheme["scheme_id"] for scheme in schemes}
    if scheme_ids is not None:
        targets &= scheme_ids

    deleted = 0
    for scheme_id in sorted(targets):
        deleted += delete_scheme_chunks(collection, scheme_id)
    return deleted


def index_chunks(
    *,
    scheme_ids: set[str] | None = None,
    rebuild: bool = False,
    refresh: bool = False,
    settings: Settings | None = None,
    embedder: Embedder | None = None,
) -> IndexResult:
    settings = settings or get_settings()
    embedder = embedder or get_embedder()

    if rebuild:
        rebuild_index(settings)

    client = get_chroma_client(settings)
    collection = get_or_create_collection(client)

    if refresh and not rebuild:
        refresh_scheme_chunks(collection, scheme_ids=scheme_ids, settings=settings)

    chunks = load_all_chunks(scheme_ids=scheme_ids, settings=settings)

    existing_ids = set(collection.get(include=[]).get("ids", []))
    to_add: list[Chunk] = []
    skipped = 0

    for chunk in chunks:
        meta = chunk.metadata
        doc_id = chunk_id(meta["scheme_id"], meta["content_hash"])
        if doc_id in existing_ids:
            skipped += 1
            continue
        to_add.append(chunk)

    if not to_add:
        return IndexResult(
            indexed_count=0,
            skipped_count=skipped,
            collection_name=COLLECTION_NAME,
            persist_dir=settings.chroma_persist_dir,
        )

    ids: list[str] = []
    documents: list[str] = []
    embed_texts: list[str] = []
    metadatas: list[dict] = []

    for chunk in to_add:
        meta = chunk.metadata
        ids.append(chunk_id(meta["scheme_id"], meta["content_hash"]))
        documents.append(chunk.text)
        embed_texts.append(
            embedder.enrich_chunk_text(meta["scheme_name"], meta["page_or_section"], chunk.text)
        )
        metadatas.append(
            {
                "scheme_id": meta["scheme_id"],
                "scheme_name": meta["scheme_name"],
                "category": meta["category"],
                "page_or_section": meta["page_or_section"],
                "content_hash": meta["content_hash"],
                "source_url": meta["source_url"],
                "source_domain": meta["source_domain"],
                "document_date": meta["document_date"],
                "document_type": meta["document_type"],
                "amc": meta["amc"],
            }
        )

    embeddings = embedder.embed_documents(embed_texts)
    collection.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)

    return IndexResult(
        indexed_count=len(to_add),
        skipped_count=skipped,
        collection_name=COLLECTION_NAME,
        persist_dir=settings.chroma_persist_dir,
    )


def collection_count(settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    client = get_chroma_client(settings)
    return get_or_create_collection(client).count()
