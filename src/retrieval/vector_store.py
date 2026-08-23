"""ChromaDB client and collection helpers."""

from __future__ import annotations

import chromadb

from src.config.settings import Settings, get_settings

COLLECTION_NAME = "scheme_chunks"


def get_chroma_client(settings: Settings | None = None) -> chromadb.PersistentClient:
    settings = settings or get_settings()
    settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(settings.chroma_persist_dir))


def get_or_create_collection(client: chromadb.PersistentClient) -> chromadb.Collection:
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
