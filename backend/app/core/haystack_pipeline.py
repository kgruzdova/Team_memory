from __future__ import annotations

from backend.app.services.rag_service import HaystackRAGService


def build_rag_pipeline() -> HaystackRAGService:
    return HaystackRAGService()

