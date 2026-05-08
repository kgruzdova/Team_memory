from backend.app.services.review_service import determine_review_state, safe_answer


def test_determine_review_state_when_no_context() -> None:
    needs_review, reason = determine_review_state(
        sources=[],
        confidence="high",
        has_context=False,
    )
    assert needs_review is True
    assert reason == "Нет релевантных фрагментов"


def test_determine_review_state_when_low_confidence() -> None:
    needs_review, reason = determine_review_state(
        sources=[{"quote": "SLA 99.9%"}],
        confidence="low",
        has_context=True,
    )
    assert needs_review is True
    assert reason == "Низкая уверенность модели"


def test_determine_review_state_when_sources_absent() -> None:
    needs_review, reason = determine_review_state(
        sources=[],
        confidence="medium",
        has_context=True,
    )
    assert needs_review is True
    assert reason == "Модель не вернула источники"


def test_safe_answer_returns_guardrail_for_manual_review() -> None:
    assert safe_answer("точный ответ", True) == "Данных недостаточно для точного ответа. Требуется ручная проверка."
    assert safe_answer("точный ответ", False) == "точный ответ"

