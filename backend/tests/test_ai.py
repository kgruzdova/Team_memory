from dataclasses import dataclass

from backend.app.api.ai import answer_with_sources
from backend.app.schemas import AIAnswerWithSourcesRequest


@dataclass
class _FakeSource:
    quote: str


@dataclass
class _FakeLLMResponse:
    answer: str
    sources: list[_FakeSource]
    confidence: str
    needs_review: bool


def test_ai_answer_with_sources_success(monkeypatch) -> None:
    def fake_ask_llm_with_context(question: str, context_docs: list[dict[str, str]]) -> _FakeLLMResponse:
        assert question == "Какой SLA?"
        assert len(context_docs) == 1
        return _FakeLLMResponse(
            answer="SLA сервиса составляет 99.9% в месяц.",
            sources=[_FakeSource(quote="SLA сервиса составляет 99.9% в месяц.")],
            confidence="high",
            needs_review=False,
        )

    monkeypatch.setattr("backend.app.api.ai.ask_llm_with_context", fake_ask_llm_with_context)
    payload = AIAnswerWithSourcesRequest(
        question="Какой SLA?",
        context="SLA сервиса составляет 99.9% в месяц.",
    )
    response = answer_with_sources(payload)
    assert response.answer.startswith("SLA сервиса")
    assert response.needs_review is False
    assert response.confidence == "high"
    assert response.sources[0].quote == "SLA сервиса составляет 99.9% в месяц."


def test_ai_answer_with_sources_fallback_on_exception(monkeypatch) -> None:
    def failing_ask_llm_with_context(question: str, context_docs: list[dict[str, str]]) -> _FakeLLMResponse:
        raise RuntimeError("OpenAI unavailable")

    monkeypatch.setattr("backend.app.api.ai.ask_llm_with_context", failing_ask_llm_with_context)
    payload = AIAnswerWithSourcesRequest(
        question="Любой вопрос",
        context="Любой контекст",
    )
    response = answer_with_sources(payload)
    assert response.answer == "данных недостаточно"
    assert response.needs_review is True
    assert response.sources == []

