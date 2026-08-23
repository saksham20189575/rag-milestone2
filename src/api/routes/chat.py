"""Chat and scheme listing endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from src.api.deps import ensure_index_ready, get_pipeline
from src.api.rate_limit import check_rate_limit
from src.api.sanitize import sanitize_message
from src.config.settings import load_schemes
from src.generation.pipeline import Pipeline

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User question about HDFC scheme facts.")


class Citation(BaseModel):
    url: str
    title: str


class ChatResponse(BaseModel):
    type: str
    text: str
    citation: Citation
    footer: str
    disclaimer: str
    intent: str | None = None


class SchemeSummary(BaseModel):
    scheme_id: str
    scheme_name: str
    category: str
    source_url: str


class SchemesResponse(BaseModel):
    schemes: list[SchemeSummary]


def _to_chat_response(payload: dict[str, Any]) -> ChatResponse:
    return ChatResponse(**payload)


@router.post("/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    request: Request,
    pipeline: Pipeline = Depends(get_pipeline),
) -> ChatResponse:
    check_rate_limit(request)
    ensure_index_ready()

    message, early_response = sanitize_message(body.message)
    if early_response is not None:
        return _to_chat_response(early_response.to_dict())

    response = pipeline.answer_query(message)
    return _to_chat_response(response.to_dict())


@router.get("/schemes", response_model=SchemesResponse)
def list_schemes() -> SchemesResponse:
    schemes = [
        SchemeSummary(
            scheme_id=scheme["scheme_id"],
            scheme_name=scheme["scheme_name"],
            category=scheme["category"],
            source_url=scheme["source_url"],
        )
        for scheme in load_schemes()
    ]
    return SchemesResponse(schemes=schemes)
