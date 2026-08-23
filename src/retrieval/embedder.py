"""Local embedding model wrapper (BGE-small)."""

from __future__ import annotations

from functools import lru_cache

from src.config.settings import get_settings


class Embedder:
    QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self._model = SentenceTransformer(model_name)

    @staticmethod
    def enrich_chunk_text(scheme_name: str, page_or_section: str, text: str) -> str:
        return f"{scheme_name} | {page_or_section} | {text}"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return vectors.tolist()

    def embed_query(self, query: str) -> list[float]:
        vector = self._model.encode(self.QUERY_PREFIX + query, normalize_embeddings=True)
        return vector.tolist()


@lru_cache
def get_embedder(model_name: str | None = None) -> Embedder:
    name = model_name or get_settings().embedding_model
    return Embedder(name)
