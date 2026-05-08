from __future__ import annotations

from backend.app.services.rag_service import HaystackRAGService


def get_pinecone_store() -> object:
    service = HaystackRAGService()
    return service.pinecone_store

