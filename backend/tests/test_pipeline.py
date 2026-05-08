import json
from pathlib import Path

import pytest

from backend.tests.run_kb_eval import evaluate_questions, read_jsonl, run_kb_evaluation


def test_read_jsonl_parses_valid_file(tmp_path: Path) -> None:
    file_path = tmp_path / "docs.jsonl"
    file_path.write_text('{"title":"A","text":"B"}\n{"title":"C","text":"D"}\n', encoding="utf-8")
    rows = read_jsonl(file_path)
    assert len(rows) == 2
    assert rows[0]["title"] == "A"


def test_read_jsonl_raises_for_invalid_json(tmp_path: Path) -> None:
    file_path = tmp_path / "bad.jsonl"
    file_path.write_text('{"title":"A"}\n{bad-json}\n', encoding="utf-8")
    with pytest.raises(ValueError):
        read_jsonl(file_path)


def test_evaluate_questions_counts_pass_fail_and_errors() -> None:
    questions = [
        {"question": "q1", "expected_needs_review": False},
        {"question": "q2", "expected_needs_review": True},
        {"question": "q3", "expected_needs_review": False},
    ]

    def ask_fn(question: str) -> dict[str, bool]:
        if question == "q1":
            return {"needs_review": False}
        if question == "q2":
            return {"needs_review": False}
        raise RuntimeError("timeout")

    summary = evaluate_questions(questions, ask_fn)
    assert summary == {"total": 3, "passed": 1, "failed": 2, "errors": 1}


def test_run_kb_evaluation_smoke_with_fake_post(tmp_path: Path) -> None:
    documents_path = tmp_path / "documents.jsonl"
    questions_path = tmp_path / "questions.jsonl"
    documents_path.write_text(
        json.dumps({"title": "Doc1", "text": "Policy"}) + "\n",
        encoding="utf-8",
    )
    questions_path.write_text(
        json.dumps({"question": "Unknown budget", "expected_needs_review": True}) + "\n",
        encoding="utf-8",
    )

    def fake_post(url: str, payload: dict[str, str]) -> dict[str, bool | str]:
        if url.endswith("/kb/documents"):
            return {"status": "ok", "document_id": "1"}
        return {"needs_review": True, "answer": "данных недостаточно"}

    summary = run_kb_evaluation(
        base_url="http://127.0.0.1:8000",
        documents_path=documents_path,
        questions_path=questions_path,
        post_fn=fake_post,
    )
    assert summary["total"] == 1
    assert summary["passed"] == 1
    assert summary["failed"] == 0

