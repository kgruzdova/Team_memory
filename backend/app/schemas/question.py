from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    question: str = Field(min_length=1)


class AskSource(BaseModel):
    document_id: str | None = None
    quote: str
    filename: str | None = None
    chunk_index: int | None = None
    page_number: int | None = None


class AskResponse(BaseModel):
    answer: str
    sources: list[AskSource]
    needs_review: bool
    review_reason: str | None


class HistoryItem(BaseModel):
    id: str
    question: str
    answer: str
    sources: list[AskSource]
    needs_review: bool
    review_reason: str | None
    error: str | None
    created_at: datetime


