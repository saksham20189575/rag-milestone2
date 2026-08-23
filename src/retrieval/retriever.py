"""Scheme-first + section-routed dense retrieval over Chroma."""

from __future__ import annotations

from dataclasses import dataclass

import chromadb

from src.config.settings import Settings, get_settings
from src.retrieval.vector_store import get_chroma_client, get_or_create_collection
from src.retrieval.embedder import Embedder, get_embedder
from src.retrieval.scheme_resolver import SchemeMatch, resolve_scheme
from src.retrieval.section_router import FUND_HOUSE_SECTION, SectionRoute, route_section

MIN_SCORE = 0.55
SECTION_BOOST = 0.15


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    score: float
    scheme_id: str
    scheme_name: str
    page_or_section: str
    source_url: str
    document_date: str
    content_hash: str


@dataclass(frozen=True)
class RetrievalResult:
    chunks: list[RetrievedChunk]
    scheme_id: str | None
    scheme_confidence: str
    routed_section: str | None
    needs_disambiguation: bool
    low_confidence: bool


class Retriever:
    def __init__(
        self,
        settings: Settings | None = None,
        embedder: Embedder | None = None,
        collection: chromadb.Collection | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.embedder = embedder or get_embedder()
        if collection is None:
            client = get_chroma_client(self.settings)
            self.collection = get_or_create_collection(client)
        else:
            self.collection = collection

    def retrieve(self, query: str) -> RetrievalResult:
        scheme_match = resolve_scheme(query)
        section_route = route_section(query)

        where = {"scheme_id": scheme_match.scheme_id} if scheme_match.scheme_id else None
        n_results = 3 if scheme_match.scheme_id else 5
        n_results = min(n_results, max(self.collection.count(), 1))

        query_embedding = self.embedder.embed_query(query)
        raw = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        ranked = self._rank_results(raw, section_route)
        top_score = ranked[0].score if ranked else 0.0

        return RetrievalResult(
            chunks=ranked[:n_results],
            scheme_id=scheme_match.scheme_id,
            scheme_confidence=scheme_match.confidence,
            routed_section=section_route.page_or_section,
            needs_disambiguation=scheme_match.confidence == "none",
            low_confidence=top_score < MIN_SCORE,
        )

    def _rank_results(
        self,
        raw: dict,
        section_route: SectionRoute,
    ) -> list[RetrievedChunk]:
        documents = raw.get("documents", [[]])[0]
        metadatas = raw.get("metadatas", [[]])[0]
        distances = raw.get("distances", [[]])[0]

        ranked: list[RetrievedChunk] = []
        for document, metadata, distance in zip(documents, metadatas, distances, strict=True):
            score = 1.0 - float(distance)
            page_or_section = metadata["page_or_section"]

            if (
                section_route.confidence == "high"
                and section_route.is_faq_fact
                and page_or_section == FUND_HOUSE_SECTION
            ):
                continue

            if (
                section_route.confidence == "high"
                and section_route.page_or_section
                and page_or_section == section_route.page_or_section
            ):
                score += SECTION_BOOST

            ranked.append(
                RetrievedChunk(
                    text=document,
                    score=score,
                    scheme_id=metadata["scheme_id"],
                    scheme_name=metadata["scheme_name"],
                    page_or_section=page_or_section,
                    source_url=metadata["source_url"],
                    document_date=metadata["document_date"],
                    content_hash=metadata["content_hash"],
                )
            )

        ranked.sort(key=lambda chunk: chunk.score, reverse=True)
        return ranked
