from __future__ import annotations

import os
from typing import Any, Callable, Literal
from uuid import uuid4

from openai import OpenAI

try:
    from pinecone import Pinecone, ServerlessSpec
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "pinecone package is required. Install it with: pip install pinecone"
    ) from exc


EmbeddingFunction = Callable[[list[str]], list[list[float]]]
# Глобальный порог косинусного сходства для решения о записи в долговременную память.
# Ниже порога -> новая информация (записываем).
# Выше или равно порогу -> дубликат/вариация (skip или update).
COSINE_SIMILARITY_THRESHOLD = float(os.getenv("COSINE_SIMILARITY_THRESHOLD", "0.85"))


class OpenAITextEmbeddingModule:
    """Модуль эмбеддинга текста через OpenAI API.

    Клиент инициализируется с `OPENAI_API_KEY` и `OPENAI_BASE_URL` из env.
    Используемая модель по умолчанию: `text-embedding-3-small`
    (можно переопределить через `OPENAI_EMBEDDING_MODEL`).
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not resolved_api_key:
            raise ValueError("OPENAI_API_KEY is required for embeddings")

        resolved_base_url = base_url or os.getenv("OPENAI_BASE_URL")
        if not resolved_base_url:
            raise ValueError("OPENAI_BASE_URL is required for embeddings")

        self.model = model or os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        self.client = OpenAI(api_key=resolved_api_key, base_url=resolved_base_url)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Создать эмбеддинги для списка текстов."""
        if not texts:
            return []
        response = self.client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]

    def __call__(self, texts: list[str]) -> list[list[float]]:
        """Синоним `embed_texts`, чтобы модуль можно было передать как функцию."""
        return self.embed_texts(texts)


class PineconeManager:
    """Единый менеджер операций чтения/записи в Pinecone.

    Поддерживает:
    - запись векторов,
    - запись текстов и документов с авто-эмбеддингом,
    - поиск по вектору и по тексту,
    - выборку/удаление/получение статистики индекса.
    """

    def __init__(
        self,
        *,
        index_name: str,
        api_key: str | None = None,
        namespace: str | None = None,
        embedding_fn: EmbeddingFunction | None = None,
        create_if_missing: bool = False,
        dimension: int | None = None,
        metric: str = "cosine",
        cloud: str = "aws",
        region: str = "us-east-1",
    ) -> None:
        self.api_key = api_key or os.getenv("PINECONE_API_KEY")
        if not self.api_key:
            raise ValueError("PINECONE_API_KEY is required")

        self.index_name = index_name
        self.default_namespace = namespace
        self.pc = Pinecone(api_key=self.api_key)

        if create_if_missing:
            self._ensure_index_exists(
                dimension=dimension,
                metric=metric,
                cloud=cloud,
                region=region,
            )

        self.index = self.pc.Index(index_name)
        self.embedding_fn = embedding_fn or self._default_embedding_fn()

    def _ensure_index_exists(
        self,
        *,
        dimension: int | None,
        metric: str,
        cloud: str,
        region: str,
    ) -> None:
        """Создать индекс, если его ещё нет в проекте Pinecone."""
        existing = {idx["name"] for idx in self.pc.list_indexes()}
        if self.index_name in existing:
            return

        if dimension is None:
            raise ValueError("dimension is required when create_if_missing=True")

        self.pc.create_index(
            name=self.index_name,
            dimension=dimension,
            metric=metric,
            spec=ServerlessSpec(cloud=cloud, region=region),
        )

    @staticmethod
    def _default_embedding_fn() -> EmbeddingFunction:
        """Вернуть функцию эмбеддинга по умолчанию через OpenAI."""
        return OpenAITextEmbeddingModule().embed_texts

    @staticmethod
    def _normalize_vector_record(record: Any) -> dict[str, Any]:
        """Нормализовать запись вектора к формату Pinecone.

        Поддерживаемые входы:
        - {"id": "...", "values": [...], "metadata": {...}}
        - {"id": "...", "vector": [...], "metadata": {...}}
        - ("id", [...], {...опциональная metadata...})
        """
        if isinstance(record, dict):
            record_id = record.get("id")
            values = record.get("values", record.get("vector"))
            metadata = record.get("metadata", {})
            if not isinstance(record_id, str) or values is None:
                raise ValueError("Vector dict must contain 'id' and 'values'/'vector'")
            return {"id": record_id, "values": values, "metadata": metadata}

        if isinstance(record, (tuple, list)) and len(record) in (2, 3):
            record_id = record[0]
            values = record[1]
            metadata = record[2] if len(record) == 3 else {}
            if not isinstance(record_id, str):
                raise ValueError("Tuple/list vector record id must be string")
            return {"id": record_id, "values": values, "metadata": metadata}

        raise ValueError("Unsupported vector record format")

    @staticmethod
    def _batched(items: list[Any], batch_size: int) -> list[list[Any]]:
        """Разбить список на батчи фиксированного размера."""
        return [items[idx : idx + batch_size] for idx in range(0, len(items), batch_size)]

    def _find_most_similar_match(
        self,
        *,
        vector: list[float],
        namespace: str | None = None,
        filter: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Найти ближайший матч по вектору (top-1)."""
        result = self.query_by_vector(
            vector,
            top_k=1,
            namespace=namespace,
            filter=filter,
            include_values=False,
            include_metadata=True,
        )
        matches = result.get("matches") or []
        if not matches:
            return None
        return matches[0]

    def _prepare_memory_record(
        self,
        *,
        text: str,
        vector: list[float],
        metadata: dict[str, Any],
        namespace: str | None,
        similarity_threshold: float,
        on_duplicate: Literal["skip", "update"],
        filter: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        """Подготовить запись для памяти с учётом порога сходства.

        Возвращает:
        - векторную запись для upsert (или None, если нужно пропустить),
        - диагностический словарь с решением и score.
        """
        best_match = self._find_most_similar_match(
            vector=vector,
            namespace=namespace,
            filter=filter,
        )

        score = None
        if best_match is not None:
            score = best_match.get("score")

        normalized_metadata = dict(metadata)
        normalized_metadata.setdefault("text", text)

        if isinstance(score, (int, float)) and score >= similarity_threshold:
            if on_duplicate == "skip":
                return None, {
                    "decision": "skipped_duplicate",
                    "score": float(score),
                    "threshold": similarity_threshold,
                    "existing_id": best_match.get("id"),
                }
            if on_duplicate == "update":
                existing_id = best_match.get("id")
                if not isinstance(existing_id, str):
                    existing_id = str(uuid4())
                return {
                    "id": existing_id,
                    "values": vector,
                    "metadata": normalized_metadata,
                }, {
                    "decision": "updated_existing",
                    "score": float(score),
                    "threshold": similarity_threshold,
                    "existing_id": existing_id,
                }

        return {
            "id": str(uuid4()),
            "values": vector,
            "metadata": normalized_metadata,
        }, {
            "decision": "inserted_new",
            "score": float(score) if isinstance(score, (int, float)) else None,
            "threshold": similarity_threshold,
            "existing_id": best_match.get("id") if best_match else None,
        }

    def upsert_vectors(
        self,
        vectors: list[Any],
        *,
        namespace: str | None = None,
        batch_size: int = 100,
    ) -> dict[str, Any]:
        """Записать готовые векторы в Pinecone."""
        normalized = [self._normalize_vector_record(item) for item in vectors]
        active_namespace = namespace or self.default_namespace
        total = 0
        for batch in self._batched(normalized, batch_size):
            self.index.upsert(vectors=batch, namespace=active_namespace)
            total += len(batch)
        return {"upserted_count": total}

    def upsert_texts(
        self,
        texts: list[str],
        *,
        ids: list[str] | None = None,
        metadatas: list[dict[str, Any]] | None = None,
        namespace: str | None = None,
        batch_size: int = 100,
        deduplicate_by_similarity: bool = False,
        similarity_threshold: float = COSINE_SIMILARITY_THRESHOLD,
        on_duplicate: Literal["skip", "update"] = "skip",
        filter: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Записать тексты: эмбеддинг + upsert.

        Если `deduplicate_by_similarity=True`, перед записью каждого текста
        выполняется поиск ближайшего фрагмента по cosine similarity:
        - score < threshold: создаётся новая память;
        - score >= threshold: `skip` (пропуск) или `update` (обновление существующей).
        """
        if not texts:
            return {"upserted_count": 0, "processed_count": 0, "decisions": []}

        generated_ids = ids or [str(uuid4()) for _ in texts]
        if len(generated_ids) != len(texts):
            raise ValueError("ids count must match texts count")

        metadatas = metadatas or [{} for _ in texts]
        if len(metadatas) != len(texts):
            raise ValueError("metadatas count must match texts count")

        embeddings = self.embedding_fn(texts)
        vectors = []
        decisions: list[dict[str, Any]] = []
        for idx, text in enumerate(texts):
            meta = dict(metadatas[idx])
            meta.setdefault("text", text)
            if deduplicate_by_similarity:
                record, decision = self._prepare_memory_record(
                    text=text,
                    vector=embeddings[idx],
                    metadata=meta,
                    namespace=namespace,
                    similarity_threshold=similarity_threshold,
                    on_duplicate=on_duplicate,
                    filter=filter,
                )
                decision["input_id"] = generated_ids[idx]
                decisions.append(decision)
                if record is not None:
                    vectors.append(record)
            else:
                vectors.append(
                    {"id": generated_ids[idx], "values": embeddings[idx], "metadata": meta}
                )
                decisions.append(
                    {"decision": "inserted_new", "score": None, "threshold": similarity_threshold}
                )

        upsert_result = self.upsert_vectors(vectors, namespace=namespace, batch_size=batch_size)
        return {
            **upsert_result,
            "processed_count": len(texts),
            "decisions": decisions,
        }

    def upsert_documents(
        self,
        documents: list[dict[str, Any] | str],
        *,
        text_key: str = "text",
        id_key: str = "id",
        metadata_key: str = "metadata",
        namespace: str | None = None,
        batch_size: int = 100,
        deduplicate_by_similarity: bool = False,
        similarity_threshold: float = COSINE_SIMILARITY_THRESHOLD,
        on_duplicate: Literal["skip", "update"] = "skip",
        filter: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Записать документы в свободном формате (dict или str).

        Поддерживает guard по косинусному сходству так же, как `upsert_texts`.
        """
        if not documents:
            return {"upserted_count": 0}

        texts: list[str] = []
        ids: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for item in documents:
            if isinstance(item, str):
                text = item
                record_id = str(uuid4())
                metadata = {}
            elif isinstance(item, dict):
                text = item.get(text_key)
                if not isinstance(text, str):
                    raise ValueError(f"Document must contain string '{text_key}'")
                record_id = str(item.get(id_key) or uuid4())
                metadata = dict(item.get(metadata_key) or {})
                for key, value in item.items():
                    if key not in {text_key, id_key, metadata_key}:
                        metadata[key] = value
            else:
                raise ValueError("Document must be dict or string")

            texts.append(text)
            ids.append(record_id)
            metadatas.append(metadata)

        return self.upsert_texts(
            texts=texts,
            ids=ids,
            metadatas=metadatas,
            namespace=namespace,
            batch_size=batch_size,
            deduplicate_by_similarity=deduplicate_by_similarity,
            similarity_threshold=similarity_threshold,
            on_duplicate=on_duplicate,
            filter=filter,
        )

    def query_by_vector(
        self,
        vector: list[float],
        *,
        top_k: int = 5,
        namespace: str | None = None,
        filter: dict[str, Any] | None = None,
        include_values: bool = False,
        include_metadata: bool = True,
    ) -> dict[str, Any]:
        """Выполнить similarity-поиск по переданному вектору."""
        return self.index.query(
            vector=vector,
            top_k=top_k,
            namespace=namespace or self.default_namespace,
            filter=filter,
            include_values=include_values,
            include_metadata=include_metadata,
        )

    def query_by_text(
        self,
        text: str,
        *,
        top_k: int = 5,
        namespace: str | None = None,
        filter: dict[str, Any] | None = None,
        include_values: bool = False,
        include_metadata: bool = True,
    ) -> dict[str, Any]:
        """Выполнить поиск по тексту: эмбеддинг текста + vector query."""
        query_vector = self.embedding_fn([text])[0]
        return self.query_by_vector(
            query_vector,
            top_k=top_k,
            namespace=namespace,
            filter=filter,
            include_values=include_values,
            include_metadata=include_metadata,
        )

    def fetch_by_ids(
        self,
        ids: list[str],
        *,
        namespace: str | None = None,
    ) -> dict[str, Any]:
        """Получить записи из индекса по списку идентификаторов."""
        return self.index.fetch(ids=ids, namespace=namespace or self.default_namespace)

    def delete(
        self,
        *,
        ids: list[str] | None = None,
        filter: dict[str, Any] | None = None,
        delete_all: bool = False,
        namespace: str | None = None,
    ) -> None:
        """Удалить записи по id, фильтру или очистить namespace целиком."""
        self.index.delete(
            ids=ids,
            filter=filter,
            delete_all=delete_all,
            namespace=namespace or self.default_namespace,
        )

    def describe_index_stats(self) -> dict[str, Any]:
        """Вернуть статистику индекса Pinecone."""
        return self.index.describe_index_stats()
