from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AIAnswerWithSourcesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    question: str = Field(min_length=1)
    context: str = Field(min_length=1)


class AIAnswerWithSourcesSource(BaseModel):
    quote: str


class AIAnswerWithSourcesResponse(BaseModel):
    answer: str
    sources: list[AIAnswerWithSourcesSource]
    confidence: Literal["high", "medium", "low"]
    needs_review: bool


