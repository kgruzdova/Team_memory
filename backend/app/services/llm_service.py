from __future__ import annotations

from typing import Any

from backend.app.services.openai_service import generate_answer_from_context, generate_single_sentence_summary
from backend.app.utils.llm_response_schema import LLMResponse


def ask_llm_with_context(question: str, context_docs: list[dict[str, Any]]) -> LLMResponse:
    return generate_answer_from_context(question, context_docs)


def summarize_document(filename: str, text: str) -> str:
    return generate_single_sentence_summary(filename, text)

