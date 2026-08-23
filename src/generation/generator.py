"""Grounded answer generation via Groq."""

from __future__ import annotations

from src.config.settings import Settings, get_settings
from src.generation.groq_client import GroqClient
from src.generation.refusal import DISCLAIMER, AssistantResponse
from src.retrieval.retriever import RetrievedChunk

SYSTEM_PROMPT = """You are a facts-only mutual fund FAQ assistant.
Answer ONLY using the provided context. Do not use outside knowledge.

Rules:
- Maximum 3 sentences.
- No investment advice, recommendations, or comparisons.
- No return calculations or predictions.
- State facts plainly.
- Do not include URLs in your answer."""

STRICT_SYSTEM_PROMPT = SYSTEM_PROMPT + """

Additional constraints:
- Use ONLY numbers and facts explicitly stated in the context.
- Do not use words such as recommend, should invest, better, guaranteed, or predict."""


def _format_context(chunks: list[RetrievedChunk]) -> str:
    blocks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        blocks.append(
            "\n".join(
                [
                    f"[Chunk {index}]",
                    f"Scheme: {chunk.scheme_name}",
                    f"Section: {chunk.page_or_section}",
                    f"Source: {chunk.source_url}",
                    f"Date: {chunk.document_date}",
                    chunk.text,
                ]
            )
        )
    return "\n\n".join(blocks)


def _primary_chunk(chunks: list[RetrievedChunk]) -> RetrievedChunk:
    return chunks[0]


def _citation_for_chunk(chunk: RetrievedChunk) -> dict[str, str]:
    return {
        "url": chunk.source_url,
        "title": f"{chunk.scheme_name} — Groww",
    }


def _footer(document_date: str) -> str:
    return f"Last updated from sources: {document_date}"


def build_answer_response(
    text: str,
    chunk: RetrievedChunk,
) -> AssistantResponse:
    return AssistantResponse(
        type="answer",
        text=text.strip(),
        citation=_citation_for_chunk(chunk),
        footer=_footer(chunk.document_date),
        disclaimer=DISCLAIMER,
    )


def build_performance_response(chunk: RetrievedChunk) -> AssistantResponse:
    text = (
        f"I cannot calculate or predict investment returns. "
        f"For performance information on {chunk.scheme_name}, "
        f"please refer to the official Groww scheme page."
    )
    return build_answer_response(text, chunk)


def build_low_confidence_response(
    *,
    scheme_name: str | None,
    source_url: str,
    document_date: str = "2026-08-21",
) -> AssistantResponse:
    if scheme_name:
        text = (
            f"I couldn't find verified information for that query in our sources. "
            f"Please refer to the official Groww page for {scheme_name}."
        )
        title = f"{scheme_name} — Groww"
    else:
        text = (
            "I couldn't find verified information for that query in our sources. "
            "Please refer to the official Groww scheme page."
        )
        title = "Mutual Funds on Groww"

    return AssistantResponse(
        type="answer",
        text=text,
        citation={"url": source_url, "title": title},
        footer=_footer(document_date),
        disclaimer=DISCLAIMER,
    )


def _chunks_for_generation(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Use only the top retrieved chunk to minimize Groq token usage."""
    return chunks[:1]


class Generator:
    def __init__(
        self,
        settings: Settings | None = None,
        groq_client: GroqClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.groq_client = groq_client or GroqClient(self.settings)

    def generate(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        *,
        strict: bool = False,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        if not chunks:
            raise ValueError("At least one retrieved chunk is required")

        generation_chunks = _chunks_for_generation(chunks)
        context = _format_context(generation_chunks)
        system = STRICT_SYSTEM_PROMPT if strict else SYSTEM_PROMPT
        user = f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer:"

        return self.groq_client.chat(
            system=system,
            user=user,
            model=model or self.settings.groq_model,
            temperature=self.settings.groq_temperature,
            max_tokens=max_tokens or self.settings.groq_generation_max_tokens,
        )

    def generate_answer(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        *,
        strict: bool = False,
    ) -> AssistantResponse:
        text = self.generate(query, chunks, strict=strict)
        return build_answer_response(text, _primary_chunk(chunks))
