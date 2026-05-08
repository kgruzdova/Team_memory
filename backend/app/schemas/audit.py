from __future__ import annotations

from pydantic import BaseModel


class ArchitectureStatusResponse(BaseModel):
    sqlite: dict[str, str]
    vector_store: str
    keyword_store: str
    embeddings_provider: str
    llm_provider: str
    backend: str
    frontend: str
    hybrid_weights: dict[str, float]


