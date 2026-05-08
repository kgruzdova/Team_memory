from __future__ import annotations

from fastapi import APIRouter

from backend.app.schemas import AIAnswerWithSourcesRequest, AIAnswerWithSourcesResponse, AIAnswerWithSourcesSource
from backend.app.services.llm_service import ask_llm_with_context
from backend.app.utils.chunking import split_into_snippets

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/answer_with_sources", response_model=AIAnswerWithSourcesResponse)
def answer_with_sources(payload: AIAnswerWithSourcesRequest) -> AIAnswerWithSourcesResponse:
    context_parts = split_into_snippets(payload.context)
    context_docs = [{"content": part} for part in (context_parts or [payload.context])]
    try:
        llm_response = ask_llm_with_context(payload.question, context_docs)
        return AIAnswerWithSourcesResponse(
            answer=llm_response.answer,
            sources=[AIAnswerWithSourcesSource(quote=source.quote) for source in llm_response.sources],
            confidence=llm_response.confidence,
            needs_review=llm_response.needs_review,
        )
    except Exception:
        return AIAnswerWithSourcesResponse(
            answer="данных недостаточно",
            sources=[],
            confidence="low",
            needs_review=True,
        )

