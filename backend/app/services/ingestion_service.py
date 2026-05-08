from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.app.repositories import add_knowledge_chunks, create_document_record
from backend.app.services.rag_service import HaystackRAGService
from backend.app.utils.chunking import split_into_snippets


class IngestionService:
    """Orchestrates ingestion flow:
    1) SQLite document record
    2) Chunking
    3) OpenAI embeddings (inside Haystack RAG service)
    4) Pinecone write (inside Haystack RAG service)
    """

    def __init__(self, rag_service: HaystackRAGService) -> None:
        self.rag_service = rag_service

    def ingest_text_document(
        self,
        db: Session,
        *,
        title: str,
        text: str,
        source: str = "manual_text_input",
    ) -> dict[str, Any]:
        snippets = split_into_snippets(text)
        if not snippets:
            raise ValueError("Document text cannot be chunked")

        document = create_document_record(db, title=title, text=text)
        db.commit()
        db.refresh(document)

        created_at = datetime.now(timezone.utc).date().isoformat()
        chunks_payload = [
            {
                "content": snippet_text,
                "document_id": str(document.id),
                "filename": title,
                "created_at": created_at,
                "chunk_index": idx,
                "page_number": None,
                "metadata_json": {"source": source},
            }
            for idx, snippet_text in enumerate(snippets, start=1)
        ]
        add_knowledge_chunks(db, document_id=document.id, chunks=chunks_payload)
        db.commit()
        rag_stats = self.rag_service.ingest_chunks(chunks_payload)
        return {
            "document_id": str(document.id),
            "chunks_total": len(chunks_payload),
            "chunks_indexed": rag_stats.get("inserted", 0),
        }

    def ingest_prechunked_document(
        self,
        db: Session,
        *,
        title: str,
        chunks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not chunks:
            raise ValueError("No chunks provided for ingestion")

        full_text = "\n\n".join(chunk["content"] for chunk in chunks)
        document = create_document_record(db, title=title, text=full_text)
        db.commit()
        db.refresh(document)

        created_at = datetime.now(timezone.utc).date().isoformat()
        for idx, chunk in enumerate(chunks, start=1):
            chunk["document_id"] = str(document.id)
            chunk["created_at"] = created_at
            if chunk.get("chunk_index") is None:
                chunk["chunk_index"] = idx

        add_knowledge_chunks(db, document_id=document.id, chunks=chunks)
        db.commit()
        rag_stats = self.rag_service.ingest_chunks(chunks)
        return {
            "document_id": str(document.id),
            "chunks_total": len(chunks),
            "chunks_indexed": rag_stats.get("inserted", 0),
            "full_text": full_text,
        }


