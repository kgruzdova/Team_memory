from __future__ import annotations

import json
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Awaitable, Callable

from fastapi import Request
from starlette.responses import Response

from backend.app.core.database import SessionLocal
from backend.app.models import AuditRun


def parse_json_bytes(payload: bytes) -> Any:
    if not payload:
        return {}
    text = payload.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


async def audit_request(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
    *,
    logger,
) -> Response:
    started_at = perf_counter()
    action = f"{request.method} {request.url.path}"
    request_body = await request.body()
    input_payload = parse_json_bytes(request_body)
    output_payload: Any = {}
    status = "success"
    error: str | None = None

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": request_body, "more_body": False}

    request_with_body = Request(request.scope, receive)
    try:
        response = await call_next(request_with_body)
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk
        output_payload = parse_json_bytes(response_body)
        if response.status_code >= 400:
            status = "error"
            if isinstance(output_payload, dict) and output_payload.get("detail") is not None:
                error = str(output_payload.get("detail"))
            else:
                error = f"HTTP {response.status_code}"
        elif (
            isinstance(output_payload, dict)
            and output_payload.get("needs_review") is True
            and output_payload.get("review_reason")
        ):
            error = str(output_payload.get("review_reason"))

        reconstructed_response = Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
            background=response.background,
        )
        return reconstructed_response
    except Exception as exc:
        logger.exception("Unhandled error while processing request: %s", action)
        status = "error"
        error = str(exc)
        output_payload = {"error": error}
        raise
    finally:
        duration_ms = int((perf_counter() - started_at) * 1000)
        db = SessionLocal()
        try:
            db.add(
                AuditRun(
                    created_at=datetime.now(timezone.utc),
                    action=action,
                    input=json.dumps(input_payload, ensure_ascii=False),
                    output=json.dumps(output_payload, ensure_ascii=False),
                    status=status,
                    error=error,
                    duration_ms=duration_ms,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

