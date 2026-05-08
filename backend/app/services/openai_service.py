from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

from openai import OpenAI

from backend.app.utils.llm_response_schema import LLMResponse, validate_llm_output

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    base_url = os.getenv("OPENAI_BASE_URL")
    if not base_url:
        raise RuntimeError("OPENAI_BASE_URL is not set")

    client_kwargs: dict[str, str] = {"api_key": api_key, "base_url": base_url}
    return OpenAI(**client_kwargs)


def generate_answer_from_context(question: str, context_docs: list[dict[str, Any]]) -> LLMResponse:
    context = "\n\n".join(doc["content"] for doc in context_docs)
    prompt = (
        "Ты отвечаешь строго в JSON.\n\n"
        "Правила:\n"
        "- отвечай ТОЛЬКО на основе context\n"
        "- не выдумывай\n"
        "- если данных мало -> needs_review=true\n"
        "- если нет источников -> needs_review=true\n\n"
        "Формат ответа:\n"
        "{\n"
        ' "answer": "...",\n'
        ' "sources": [{"quote": "..."}],\n'
        ' "confidence": "high|medium|low",\n'
        ' "needs_review": true/false\n'
        "}\n\n"
        "question:\n"
        f"{question}\n\n"
        "context:\n"
        f"{context}"
    )

    completion = get_openai_client().chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты ассистент базы знаний. Все ответы формируй через OpenAI API и возвращай строго JSON."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )
    content = completion.choices[0].message.content
    if not content:
        raise RuntimeError("OpenAI returned empty response content")
    return validate_llm_output(content)


def generate_single_sentence_summary(filename: str, text: str) -> str:
    prompt = (
        "Сделай очень краткое резюме файла ровно в одном предложении на русском языке, "
        "без маркированных списков.\n\n"
        f"Название файла: {filename}\n"
        f"Содержимое:\n{text[:8000]}"
    )
    completion = get_openai_client().chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": "Ты возвращаешь только одну строку-резюме, строго одно предложение.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    content = completion.choices[0].message.content
    if not content:
        return "Файл содержит информацию, которая добавлена в базу знаний."

    clean = " ".join(content.strip().split())
    clean = clean.rstrip(".!?")
    return f"{clean}."


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    response = get_openai_client().embeddings.create(
        model=OPENAI_EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)

