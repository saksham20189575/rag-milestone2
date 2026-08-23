"""End-to-end RAG pipeline: classify → retrieve → generate → validate."""

from __future__ import annotations

from src.config.settings import Settings, get_settings, load_schemes
from src.generation.classifier import classify_query
from src.generation.generator import (
    Generator,
    build_answer_response,
    build_low_confidence_response,
)
from src.generation.rate_limiter import GroqRateLimitExceeded
from src.generation.refusal import AssistantResponse, build_refusal, refusal_from_classification
from src.generation.validator import validate_answer
from src.retrieval.retriever import Retriever, RetrievedChunk


def _scheme_source_url(scheme_id: str | None) -> tuple[str | None, str | None]:
    if not scheme_id:
        return None, None
    for scheme in load_schemes():
        if scheme["scheme_id"] == scheme_id:
            return scheme["scheme_name"], scheme["source_url"]
    return None, None


def _dedupe_chunks_by_section(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Prefer the first chunk per section; retriever ranking already boosts routed sections."""
    seen: set[str] = set()
    ordered: list[RetrievedChunk] = []
    for chunk in chunks:
        key = f"{chunk.scheme_id}:{chunk.page_or_section}"
        if key in seen:
            continue
        seen.add(key)
        ordered.append(chunk)
    return ordered or chunks


class Pipeline:
    def __init__(
        self,
        settings: Settings | None = None,
        retriever: Retriever | None = None,
        generator: Generator | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.retriever = retriever or Retriever(self.settings)
        self.generator = generator or Generator(self.settings)

    def answer_query(
        self,
        message: str,
        *,
        use_groq_classifier: bool = False,
    ) -> AssistantResponse:
        classification = classify_query(message, use_groq=use_groq_classifier)
        refusal = refusal_from_classification(classification)
        if refusal is not None:
            return refusal

        retrieval = self.retriever.retrieve(message)
        chunks = _dedupe_chunks_by_section(retrieval.chunks)

        scheme_name, scheme_url = _scheme_source_url(retrieval.scheme_id)
        fallback_url = scheme_url or (
            chunks[0].source_url if chunks else self.settings.refusal_citation_url
        )
        fallback_date = chunks[0].document_date if chunks else "2026-08-21"

        if retrieval.needs_disambiguation and retrieval.scheme_id is None:
            return build_refusal("out_of_scope")

        if retrieval.low_confidence or not chunks:
            return build_low_confidence_response(
                scheme_name=scheme_name,
                source_url=fallback_url,
                document_date=fallback_date,
            )

        chunk_urls = tuple(chunk.source_url for chunk in chunks)
        primary = chunks[0]

        attempts: tuple[tuple[bool, bool], ...] = (
            (False, False),  # primary model, normal prompt
            (True, True),    # fast model, strict prompt (saves primary quota)
        )

        for strict, use_fast_model in attempts:
            try:
                if use_fast_model:
                    text = self.generator.generate(
                        message,
                        chunks,
                        strict=strict,
                        model=self.settings.groq_model_fast,
                        max_tokens=self.settings.groq_max_tokens,
                    )
                else:
                    text = self.generator.generate(message, chunks, strict=strict)
            except GroqRateLimitExceeded:
                return build_low_confidence_response(
                    scheme_name=primary.scheme_name,
                    source_url=primary.source_url,
                    document_date=primary.document_date,
                )

            response = build_answer_response(text, primary)
            validation = validate_answer(
                response,
                allowed_chunk_urls=chunk_urls,
                settings=self.settings,
            )
            if validation.valid:
                return response

        return build_low_confidence_response(
            scheme_name=primary.scheme_name,
            source_url=primary.source_url,
            document_date=primary.document_date,
        )


def answer_query(
    message: str,
    *,
    use_groq_classifier: bool = False,
    pipeline: Pipeline | None = None,
) -> AssistantResponse:
    """Run the full facts-only RAG pipeline for a user message."""
    runner = pipeline or Pipeline()
    return runner.answer_query(message, use_groq_classifier=use_groq_classifier)
