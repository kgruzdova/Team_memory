from __future__ import annotations

from typing import Any

from backend.app.services.rag_service import HaystackRAGService


def retrieve_answer(rag_service: HaystackRAGService, question: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return rag_service.answer(question)

