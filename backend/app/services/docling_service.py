from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from docling_haystack.converter import DoclingConverter, ExportType
from haystack import Pipeline
from haystack.dataclasses import Document as HaystackDocument


def _parse_docling_meta(meta: Any) -> dict[str, Any]:
    if isinstance(meta, dict):
        return meta
    if isinstance(meta, str):
        try:
            parsed = json.loads(meta)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
    return {}


def _extract_page_number(dl_meta: dict[str, Any]) -> int | None:
    try:
        doc_items = dl_meta.get("doc_items") or []
        if not doc_items:
            return None
        prov = doc_items[0].get("prov") or []
        if not prov:
            return None
        page_no = prov[0].get("page_no")
        if isinstance(page_no, int):
            return page_no
    except Exception:
        return None
    return None


class DoclingIngestionService:
    def __init__(self) -> None:
        self.ingestion_pipeline = Pipeline()
        self.ingestion_pipeline.add_component(
            "converter",
            DoclingConverter(
                export_type=ExportType.DOC_CHUNKS,
            ),
        )

    def _split_plain_text(self, text: str, max_chars: int = 1800) -> list[str]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return []

        chunks: list[str] = []
        current: list[str] = []
        current_len = 0
        for line in lines:
            line_len = len(line) + 1
            if current and current_len + line_len > max_chars:
                chunks.append("\n".join(current))
                current = [line]
                current_len = line_len
            else:
                current.append(line)
                current_len += line_len
        if current:
            chunks.append("\n".join(current))
        return chunks

    def _convert_plain_text_file(self, file_path: str, fallback_name: str | None = None) -> list[dict[str, Any]]:
        filename = fallback_name or Path(file_path).name
        raw_text = Path(file_path).read_text(encoding="utf-8", errors="replace")
        text_chunks = self._split_plain_text(raw_text)
        return [
            {
                "content": chunk_text,
                "filename": filename,
                "chunk_index": idx,
                "page_number": None,
                "metadata_json": {"source": "plain_text_loader"},
            }
            for idx, chunk_text in enumerate(text_chunks, start=1)
        ]

    def convert_source_to_chunks(self, source_path: str, fallback_name: str | None = None) -> list[dict[str, Any]]:
        result = self.ingestion_pipeline.run({"converter": {"paths": [source_path]}})
        documents = result["converter"]["documents"]
        filename = fallback_name or Path(source_path).name
        chunks: list[dict[str, Any]] = []
        for index, doc in enumerate(documents, start=1):
            if not isinstance(doc, HaystackDocument):
                continue
            raw_meta = doc.meta or {}
            dl_meta = _parse_docling_meta(raw_meta.get("dl_meta"))
            origin_name = (
                (dl_meta.get("origin") or {}).get("filename")
                if isinstance(dl_meta.get("origin"), dict)
                else None
            )
            chunks.append(
                {
                    "content": doc.content,
                    "filename": origin_name or filename,
                    "chunk_index": index,
                    "page_number": _extract_page_number(dl_meta),
                    "metadata_json": raw_meta if isinstance(raw_meta, dict) else {},
                }
            )
        return chunks

    def convert_file_to_chunks(self, file_path: str, fallback_name: str | None = None) -> list[dict[str, Any]]:
        suffix = Path(file_path).suffix.lower()
        if suffix in {".txt", ".csv", ".md", ".log"}:
            return self._convert_plain_text_file(file_path, fallback_name=fallback_name)
        return self.convert_source_to_chunks(file_path, fallback_name=fallback_name)

