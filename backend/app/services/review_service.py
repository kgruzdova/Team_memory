from __future__ import annotations

from typing import Any


def determine_review_state(
    *,
    sources: list[dict[str, Any]],
    confidence: str,
    has_context: bool,
) -> tuple[bool, str | None]:
    if not has_context:
        return True, "Нет релевантных фрагментов"
    if confidence == "low":
        return True, "Низкая уверенность модели"
    if len(sources) == 0:
        return True, "Модель не вернула источники"
    return False, None


def safe_answer(answer: str, needs_review: bool) -> str:
    if needs_review:
        return "Данных недостаточно для точного ответа. Требуется ручная проверка."
    return answer

