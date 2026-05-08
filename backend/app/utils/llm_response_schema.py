from __future__ import annotations

import json
from typing import Any
from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr, model_validator


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    quote: StrictStr


class LLMResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    answer: StrictStr
    sources: list[Source]
    confidence: Literal["high", "medium", "low"]
    needs_review: StrictBool

    @model_validator(mode="after")
    def validate_sources_and_review_flag(self) -> "LLMResponse":
        if len(self.sources) == 0 and self.needs_review is not True:
            raise ValueError("needs_review must be true when sources is empty")
        return self


def validate_llm_output(raw_output: str | dict[str, Any]) -> LLMResponse:
    if isinstance(raw_output, str):
        parsed: Any = json.loads(raw_output)
    else:
        parsed = raw_output

    validated = LLMResponse.model_validate(parsed)
    needs_review = validated.needs_review
    if validated.confidence == "low":
        needs_review = True
    if len(validated.sources) == 0:
        needs_review = True

    return LLMResponse(
        answer=validated.answer,
        sources=validated.sources,
        confidence=validated.confidence,
        needs_review=needs_review,
    )

