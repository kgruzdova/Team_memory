from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.models import Base
from backend.app.repositories import (
    add_knowledge_chunks,
    clear_all_documents,
    create_document_record,
    list_documents,
    list_qa_history,
    save_qa_run,
)


def _build_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_factory()


def test_document_and_chunk_persistence_flow() -> None:
    db = _build_session()
    try:
        doc = create_document_record(db, title="Runbook", text="Step 1\n\nStep 2")
        db.commit()
        db.refresh(doc)
        assert doc.id > 0

        chunks = [
            {
                "content": "Step 1",
                "filename": "Runbook",
                "chunk_index": 1,
                "page_number": None,
                "metadata_json": {"source": "unit_test"},
            },
            {
                "content": "Step 2",
                "filename": "Runbook",
                "chunk_index": 2,
                "page_number": None,
                "metadata_json": {"source": "unit_test"},
            },
        ]
        rows = add_knowledge_chunks(db, document_id=doc.id, chunks=chunks)
        db.commit()

        assert len(rows) == 2
        assert rows[0].document_id == doc.id
        assert rows[0].metadata_json == {"source": "unit_test"}

        docs = list_documents(db)
        assert len(docs) == 1
        assert docs[0].title == "Runbook"
    finally:
        db.close()


def test_history_and_clear_documents() -> None:
    db = _build_session()
    try:
        doc = create_document_record(db, title="FAQ", text="A")
        db.commit()
        save_qa_run(
            db,
            question="Q1",
            answer="A1",
            sources_json=[{"quote": "A"}],
            needs_review=False,
            review_reason=None,
            error=None,
        )
        history = list_qa_history(db, needs_review=None)
        assert len(history) == 1
        assert history[0].question == "Q1"

        deleted = clear_all_documents(db)
        assert deleted == 1
        assert list_documents(db) == []
        assert doc.id > 0
    finally:
        db.close()

