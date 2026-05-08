from __future__ import annotations

from functools import lru_cache

from backend.app.services.docling_service import DoclingIngestionService
from backend.app.services.ingestion_service import IngestionService
from backend.app.services.rag_service import HaystackRAGService


@lru_cache(maxsize=1)
def get_rag_service() -> HaystackRAGService:
    return HaystackRAGService()


@lru_cache(maxsize=1)
def get_docling_service() -> DoclingIngestionService:
    return DoclingIngestionService()


@lru_cache(maxsize=1)
def get_ingestion_service() -> IngestionService:
    return IngestionService(rag_service=get_rag_service())

