"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from src.ingestion.indexer import collection_count, index_chunks
from src.retrieval.retriever import Retriever


@pytest.fixture(scope="session")
def indexed_retriever() -> Retriever:
    result = index_chunks(rebuild=True)
    assert result.indexed_count == 31
    assert collection_count() == 31
    return Retriever()
