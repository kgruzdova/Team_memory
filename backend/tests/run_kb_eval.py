from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for index, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL in {path} at line {index}: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"JSONL line {index} in {path} must be an object")
            rows.append(row)
    return rows


def post_json(url: str, payload: dict[str, Any], timeout_seconds: int = 20) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url=url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {error_body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Failed to call {url}: {exc}") from exc

    try:
        parsed = json.loads(response_body) if response_body else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON response from {url}: {response_body}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Expected JSON object from {url}, got: {parsed!r}")
    return parsed


def evaluate_questions(
    questions: list[dict[str, Any]],
    ask_fn: Callable[[str], dict[str, Any]],
) -> dict[str, int]:
    total = 0
    passed = 0
    failed = 0
    errors = 0
    for index, item in enumerate(questions, start=1):
        question = item.get("question")
        expected = item.get("expected_needs_review")
        if not isinstance(question, str) or not isinstance(expected, bool):
            raise ValueError(
                f"Question line {index} must include 'question': str and "
                f"'expected_needs_review': bool"
            )
        total += 1
        try:
            response = ask_fn(question)
            actual = response.get("needs_review")
            if not isinstance(actual, bool):
                raise RuntimeError(f"Invalid response payload: {response}")
            if actual == expected:
                passed += 1
            else:
                failed += 1
        except Exception:
            errors += 1
            failed += 1
    return {"total": total, "passed": passed, "failed": failed, "errors": errors}


def run_kb_evaluation(
    *,
    base_url: str,
    documents_path: Path,
    questions_path: Path,
    post_fn: Callable[[str, dict[str, Any]], dict[str, Any]] = post_json,
) -> dict[str, int]:
    documents = read_jsonl(documents_path)
    questions = read_jsonl(questions_path)

    documents_url = f"{base_url.rstrip('/')}/kb/documents"
    ask_url = f"{base_url.rstrip('/')}/kb/ask"

    for index, doc in enumerate(documents, start=1):
        title = doc.get("title")
        text = doc.get("text")
        if not isinstance(title, str) or not isinstance(text, str):
            raise ValueError(
                f"Document line {index} must include string fields 'title' and 'text'"
            )
        post_fn(documents_url, {"title": title, "text": text})

    def ask(question: str) -> dict[str, Any]:
        return post_fn(ask_url, {"question": question})

    return evaluate_questions(questions, ask)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate KB endpoints with JSONL test data.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="FastAPI base URL")
    parser.add_argument(
        "--documents",
        default="backend/tests_data/kb_documents.jsonl",
        help="Path to JSONL with documents",
    )
    parser.add_argument(
        "--questions",
        default="backend/tests_data/kb_questions.jsonl",
        help="Path to JSONL with questions and expected_needs_review",
    )
    args = parser.parse_args()

    summary = run_kb_evaluation(
        base_url=args.base_url,
        documents_path=Path(args.documents),
        questions_path=Path(args.questions),
    )
    print("Summary:")
    print(f"  total:  {summary['total']}")
    print(f"  passed: {summary['passed']}")
    print(f"  failed: {summary['failed']}")
    print(f"  errors: {summary['errors']}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

