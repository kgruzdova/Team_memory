from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.repositories import clear_all_documents, list_documents


def list_documents_rows(db: Session):
    return list_documents(db)


def clear_documents_rows(db: Session) -> int:
    return clear_all_documents(db)

