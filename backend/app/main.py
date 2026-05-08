from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from backend.app.api import ai_router, audit_router, health_router, kb_router
from backend.app.core.config import settings
from backend.app.core.database import SessionLocal, init_db
from backend.app.dependencies import get_rag_service
from backend.app.repositories import list_all_knowledge_chunks
from backend.app.services.audit_service import audit_request
from backend.app.utils.logger import get_logger

logger = get_logger("team_memory")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ENV_FILE = PROJECT_ROOT / "backend" / ".env"
load_dotenv(BACKEND_ENV_FILE)
load_dotenv(PROJECT_ROOT / ".env")

app = FastAPI(title=settings.app_title)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin_localhost, settings.frontend_origin_loopback],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def audit_all_api_calls(request: Request, call_next):  # type: ignore[no-untyped-def]
    return await audit_request(request, call_next, logger=logger)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    db = SessionLocal()
    try:
        chunks = list_all_knowledge_chunks(db)
        warmup_payload = [
            {
                "content": row.content,
                "document_id": str(row.document_id),
                "filename": row.filename,
                "created_at": row.created_at.date().isoformat(),
                "chunk_index": row.chunk_index,
                "page_number": row.page_number,
                "metadata_json": row.metadata_json or {},
            }
            for row in chunks
        ]
        get_rag_service().bootstrap_keyword_store(warmup_payload)
    finally:
        db.close()


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "team-memory-backend", "status": "ok"}


app.include_router(health_router)
app.include_router(kb_router)
app.include_router(ai_router)
app.include_router(audit_router)

