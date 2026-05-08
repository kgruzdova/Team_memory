from __future__ import annotations


def split_into_snippets(text: str) -> list[str]:
    parts = text.split("\n\n")
    return [part for part in parts if part.strip()]


