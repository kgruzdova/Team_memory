from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from backend.app.core.database import SessionLocal
from backend.app.models import AuditRun

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/latest")
def latest_audit(limit: int = 20) -> list[dict[str, str | int | None]]:
    db = SessionLocal()
    try:
        rows = db.scalars(select(AuditRun).order_by(AuditRun.created_at.desc())).all()[:limit]
        return [
            {
                "id": row.id,
                "action": row.action,
                "status": row.status,
                "error": row.error,
                "duration_ms": row.duration_ms,
            }
            for row in rows
        ]
    finally:
        db.close()

