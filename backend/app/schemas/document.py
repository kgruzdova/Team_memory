from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class DocumentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1, max_length=200000)


class DocumentCreateResponse(BaseModel):
    status: str
    document_id: str


class FileIngestResponse(BaseModel):
    status: str
    document_id: str
    message: str
    summary: str


class UrlIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    url: HttpUrl
    title: str | None = Field(default=None, min_length=1, max_length=500)


class DocumentListItem(BaseModel):
    id: str
    title: str
    created_at: date


class DocumentsClearResponse(BaseModel):
    status: str
    deleted_documents: int
    deleted_pinecone_chunks: int
    deleted_keyword_chunks: int


