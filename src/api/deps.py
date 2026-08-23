"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import HTTPException

from src.generation.pipeline import Pipeline
from src.ingestion.indexer import collection_count

_pipeline: Pipeline | None = None


def get_pipeline() -> Pipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = Pipeline()
    return _pipeline


def reset_pipeline() -> None:
    """Reset the cached pipeline instance (for tests)."""
    global _pipeline
    _pipeline = None


def ensure_index_ready() -> None:
    if collection_count() == 0:
        raise HTTPException(
            status_code=503,
            detail="Corpus not indexed — run: python scripts/ingest.py --scheme all",
        )
