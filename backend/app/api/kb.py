from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.dependencies import get_docling_service, get_ingestion_service, get_rag_service
from backend.app.schemas import (
    ArchitectureStatusResponse,
    AskRequest,
    AskResponse,
    AskSource,
    DocumentCreateRequest,
    DocumentCreateResponse,
    DocumentListItem,
    DocumentsClearResponse,
    FileIngestResponse,
    HistoryItem,
    UrlIngestRequest,
)
from backend.app.services.document_service import clear_documents_rows, list_documents_rows
from backend.app.services.llm_service import summarize_document
from backend.app.services.review_service import determine_review_state, safe_answer
from backend.app.repositories import list_qa_history, save_qa_run

router = APIRouter(prefix="/kb", tags=["kb"])


@router.post("/documents", response_model=DocumentCreateResponse)
def create_document(
    payload: DocumentCreateRequest,
    db: Session = Depends(get_db),
) -> DocumentCreateResponse:
    result = get_ingestion_service().ingest_text_document(
        db,
        title=payload.title,
        text=payload.text,
        source="manual_text_input",
    )
    return DocumentCreateResponse(status="ok", document_id=result["document_id"])


@router.post("/files", response_model=FileIngestResponse)
async def upload_file_to_kb(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> FileIngestResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    suffix = Path(file.filename).suffix
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Файл пустой")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        chunks = get_docling_service().convert_file_to_chunks(tmp_path, fallback_name=file.filename)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Ошибка обработки файла через Docling: {exc}") from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if not chunks:
        raise HTTPException(status_code=400, detail="Не удалось извлечь контент из файла")
    result = get_ingestion_service().ingest_prechunked_document(
        db,
        title=file.filename,
        chunks=chunks,
    )
    document_id = result["document_id"]
    full_text = result["full_text"]
    summary = summarize_document(file.filename, full_text)
    return FileIngestResponse(
        status="ok",
        document_id=document_id,
        message="Готово. Я изучил этот файл, теперь можем его обсудить.",
        summary=summary,
    )


@router.post("/urls", response_model=FileIngestResponse)
def upload_url_to_kb(
    payload: UrlIngestRequest,
    db: Session = Depends(get_db),
) -> FileIngestResponse:
    source_url = str(payload.url)
    source_title = payload.title or source_url
    try:
        chunks = get_docling_service().convert_source_to_chunks(source_url, fallback_name=source_title)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Ошибка обработки URL через Docling: {exc}") from exc

    if not chunks:
        raise HTTPException(status_code=400, detail="Не удалось извлечь контент из URL")
    result = get_ingestion_service().ingest_prechunked_document(
        db,
        title=source_title,
        chunks=chunks,
    )
    document_id = result["document_id"]
    full_text = result["full_text"]
    summary = summarize_document(source_title, full_text)
    return FileIngestResponse(
        status="ok",
        document_id=document_id,
        message="Готово. Я изучил этот файл, теперь можем его обсудить.",
        summary=summary,
    )


@router.get("/documents", response_model=list[DocumentListItem])
def get_documents(db: Session = Depends(get_db)) -> list[DocumentListItem]:
    return [
        DocumentListItem(
            id=str(item.id),
            title=item.title,
            created_at=item.created_at.date(),
        )
        for item in list_documents_rows(db)
    ]


@router.delete("/documents", response_model=DocumentsClearResponse)
def clear_documents(db: Session = Depends(get_db)) -> DocumentsClearResponse:
    deleted_documents = clear_documents_rows(db)
    deleted_chunks = get_rag_service().clear_knowledge_chunks()
    return DocumentsClearResponse(
        status="ok",
        deleted_documents=deleted_documents,
        deleted_pinecone_chunks=deleted_chunks.get("pinecone", 0),
        deleted_keyword_chunks=deleted_chunks.get("keyword", 0),
    )


@router.post("/ask", response_model=AskResponse)
def ask_question(payload: AskRequest, db: Session = Depends(get_db)) -> AskResponse:
    try:
        model_output, context_docs = get_rag_service().answer(payload.question)
        needs_review, review_reason = determine_review_state(
            sources=model_output["sources"],
            confidence=model_output["confidence"],
            has_context=len(context_docs) > 0,
        )
        response = AskResponse(
            answer=safe_answer(model_output["answer"], needs_review),
            sources=[AskSource(**source) for source in model_output["sources"]],
            needs_review=needs_review,
            review_reason=review_reason,
        )
        try:
            save_qa_run(
                db,
                question=payload.question,
                answer=response.answer,
                sources_json=[source.model_dump() for source in response.sources],
                needs_review=response.needs_review,
                review_reason=response.review_reason,
                error=None,
            )
        except Exception:
            db.rollback()
        return response
    except Exception as exc:
        response = AskResponse(
            answer=safe_answer("данных недостаточно", True),
            sources=[],
            needs_review=True,
            review_reason="Ошибка при обработке запроса",
        )
        try:
            save_qa_run(
                db,
                question=payload.question,
                answer=response.answer,
                sources_json=[],
                needs_review=response.needs_review,
                review_reason=response.review_reason,
                error=str(exc),
            )
        except Exception:
            db.rollback()
        return response


@router.get("/history", response_model=list[HistoryItem])
def get_history(
    needs_review: bool | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[HistoryItem]:
    rows = list_qa_history(db, needs_review)[:100]

    def normalize_sources(raw: Any) -> list[dict[str, Any]]:
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
        if isinstance(raw, dict):
            return [raw]
        return []

    return [
        HistoryItem(
            id=str(row.id),
            question=row.question,
            answer=row.answer,
            sources=[AskSource(**source) for source in normalize_sources(row.sources_json)],
            needs_review=row.needs_review,
            review_reason=row.review_reason,
            error=row.error,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/architecture", response_model=ArchitectureStatusResponse)
def get_architecture_status() -> ArchitectureStatusResponse:
    snapshot = get_rag_service().architecture_snapshot()
    return ArchitectureStatusResponse(**snapshot)

