from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Document, KnowledgeChunk, QARun


def create_document_record(db: Session, title: str, text: str) -> Document:
    document = Document(title=title, text=text)
    db.add(document)
    db.flush()
    return document


def add_knowledge_chunks(
    db: Session,
    *,
    document_id: int,
    chunks: list[dict[str, Any]],
) -> list[KnowledgeChunk]:
    rows: list[KnowledgeChunk] = []
    for chunk in chunks:
        row = KnowledgeChunk(
            document_id=document_id,
            content=chunk["content"],
            filename=chunk.get("filename"),
            chunk_index=chunk.get("chunk_index"),
            page_number=chunk.get("page_number"),
            metadata_json=chunk.get("metadata_json"),
        )
        db.add(row)
        rows.append(row)
    db.flush()
    return rows


def list_documents(db: Session) -> list[Document]:
    return db.scalars(select(Document).order_by(Document.created_at.desc())).all()


def list_qa_history(db: Session, needs_review: bool | None) -> list[QARun]:
    stmt = select(QARun).order_by(QARun.created_at.desc())
    if needs_review is not None:
        stmt = stmt.where(QARun.needs_review == needs_review)
    return db.scalars(stmt).all()


def save_qa_run(
    db: Session,
    *,
    question: str,
    answer: str,
    sources_json: list[dict[str, Any]],
    needs_review: bool,
    review_reason: str | None,
    error: str | None,
) -> None:
    db.add(
        QARun(
            question=question,
            answer=answer,
            sources_json=sources_json,
            needs_review=needs_review,
            review_reason=review_reason if needs_review else None,
            error=error,
        )
    )
    db.commit()


def list_all_knowledge_chunks(db: Session) -> list[KnowledgeChunk]:
    return db.scalars(select(KnowledgeChunk).order_by(KnowledgeChunk.id.asc())).all()


def clear_all_documents(db: Session) -> int:
    rows = db.scalars(select(Document)).all()
    deleted_count = len(rows)
    for row in rows:
        db.delete(row)
    db.commit()
    return deleted_count

