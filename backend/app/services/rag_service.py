from __future__ import annotations

import json
import os
from difflib import SequenceMatcher
from typing import Any
from uuid import uuid4

from haystack import Document, Pipeline
from haystack.components.embedders import OpenAIDocumentEmbedder, OpenAITextEmbedder
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever
from haystack.components.writers import DocumentWriter
from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack.utils import Secret
from haystack_integrations.components.retrievers.pinecone import PineconeEmbeddingRetriever
from haystack_integrations.document_stores.pinecone import PineconeDocumentStore

from backend.app.services.openai_service import generate_answer_from_context


class HaystackRAGService:
    def __init__(self) -> None:
        self.pinecone_store: PineconeDocumentStore | None = None
        self.keyword_store: InMemoryDocumentStore | None = None
        self.ingestion_pipeline: Pipeline | None = None
        self.text_embedder: OpenAITextEmbedder | None = None
        self.vector_retriever: PineconeEmbeddingRetriever | None = None
        self.keyword_retriever: InMemoryBM25Retriever | None = None
        self.vector_top_k = int(os.getenv("VECTOR_TOP_K", "6"))
        self.keyword_top_k = int(os.getenv("KEYWORD_TOP_K", "6"))
        self.hybrid_top_k = int(os.getenv("HYBRID_TOP_K", "6"))
        self._setup_pipelines()

    def _setup_pipelines(self) -> None:
        openai_api_key = os.getenv("OPENAI_API_KEY", "")
        openai_base_url = os.getenv("OPENAI_BASE_URL", "")
        openai_embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        pinecone_index_name = os.getenv("PINECONE_INDEX_NAME", "team-memory")
        pinecone_dimension = int(os.getenv("PINECONE_DIMENSION", "1536"))
        pinecone_metric = os.getenv("PINECONE_METRIC", "cosine")
        pinecone_cloud = os.getenv("PINECONE_CLOUD", "aws")
        pinecone_region = os.getenv("PINECONE_REGION", "us-east-1")
        pinecone_namespace = os.getenv("PINECONE_NAMESPACE", "default")

        if not openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required")
        if not openai_base_url:
            raise RuntimeError("OPENAI_BASE_URL is required")

        self.pinecone_store = PineconeDocumentStore(
            index=pinecone_index_name,
            metric=pinecone_metric,
            dimension=pinecone_dimension,
            spec={"serverless": {"region": pinecone_region, "cloud": pinecone_cloud}},
            namespace=pinecone_namespace,
        )
        self.keyword_store = InMemoryDocumentStore()

        self.text_embedder = OpenAITextEmbedder(
            api_key=Secret.from_token(openai_api_key),
            api_base_url=openai_base_url,
            model=openai_embedding_model,
        )
        document_embedder = OpenAIDocumentEmbedder(
            api_key=Secret.from_token(openai_api_key),
            api_base_url=openai_base_url,
            model=openai_embedding_model,
        )
        self.vector_retriever = PineconeEmbeddingRetriever(
            document_store=self.pinecone_store,
            top_k=self.vector_top_k,
        )
        self.keyword_retriever = InMemoryBM25Retriever(
            document_store=self.keyword_store,
            top_k=self.keyword_top_k,
        )

        self.ingestion_pipeline = Pipeline()
        self.ingestion_pipeline.add_component("embedder", document_embedder)
        self.ingestion_pipeline.add_component("pinecone_writer", DocumentWriter(document_store=self.pinecone_store))
        self.ingestion_pipeline.add_component("keyword_writer", DocumentWriter(document_store=self.keyword_store))
        self.ingestion_pipeline.connect("embedder.documents", "pinecone_writer.documents")
        self.ingestion_pipeline.connect("embedder.documents", "keyword_writer.documents")

    def _to_haystack_documents(self, chunks: list[dict[str, Any]]) -> list[Document]:
        docs: list[Document] = []
        for chunk in chunks:
            meta: dict[str, Any] = {
                "record_type": "knowledge_chunk",
                "document_id": chunk.get("document_id"),
                "filename": chunk.get("filename"),
                "created_at": chunk.get("created_at"),
                "chunk_index": chunk.get("chunk_index"),
            }
            page_number = chunk.get("page_number")
            if isinstance(page_number, int):
                meta["page_number"] = page_number

            extra_meta = chunk.get("metadata_json") if isinstance(chunk.get("metadata_json"), dict) else {}
            for key, value in extra_meta.items():
                if value is None:
                    continue
                if isinstance(value, (str, int, bool)):
                    meta[key] = value
                elif isinstance(value, list) and all(isinstance(item, str) for item in value):
                    meta[key] = value
                else:
                    meta[f"{key}_json"] = json.dumps(value, ensure_ascii=False)

            document_id = str(chunk.get("document_id") or "unknown")
            chunk_index = int(chunk.get("chunk_index") or 0)
            docs.append(
                Document(
                    id=f"{document_id}:{chunk_index}:{uuid4()}",
                    content=chunk["content"],
                    meta=meta,
                )
            )
        return docs

    def _find_source_meta(self, quote: str, context_docs: list[dict[str, Any]]) -> dict[str, Any] | None:
        normalized_quote = " ".join(quote.strip().split()).lower()
        if not normalized_quote:
            return None

        best_meta: dict[str, Any] | None = None
        best_score = 0.0
        for doc in context_docs:
            content = doc["content"]
            normalized_content = " ".join(content.strip().split()).lower()
            if normalized_quote == normalized_content:
                return doc["meta"]
            if normalized_quote in normalized_content:
                return doc["meta"]
            if normalized_content in normalized_quote:
                return doc["meta"]
            ratio = SequenceMatcher(None, normalized_quote, normalized_content).ratio()
            if ratio > best_score:
                best_score = ratio
                best_meta = doc["meta"]

        if best_score >= 0.65:
            return best_meta
        return None

    @staticmethod
    def _normalize_scores(docs: list[Document]) -> dict[str, float]:
        raw_scores: dict[str, float] = {}
        for doc in docs:
            if doc.id is None:
                continue
            score = getattr(doc, "score", None)
            if isinstance(score, (float, int)):
                raw_scores[str(doc.id)] = float(score)
        if not raw_scores:
            return {}
        max_score = max(raw_scores.values())
        if max_score <= 0:
            return {doc_id: 0.0 for doc_id in raw_scores}
        return {doc_id: score / max_score for doc_id, score in raw_scores.items()}

    def _hybrid_rank(self, vector_docs: list[Document], keyword_docs: list[Document]) -> list[Document]:
        by_id: dict[str, Document] = {}
        vector_norm = self._normalize_scores(vector_docs)
        keyword_norm = self._normalize_scores(keyword_docs)

        for doc in vector_docs + keyword_docs:
            if doc.id is None:
                continue
            by_id[str(doc.id)] = doc

        ranked: list[tuple[float, Document]] = []
        for doc_id, doc in by_id.items():
            score = 0.65 * vector_norm.get(doc_id, 0.0) + 0.35 * keyword_norm.get(doc_id, 0.0)
            if doc_id in vector_norm and doc_id in keyword_norm:
                score += 0.1
            ranked.append((score, doc))

        ranked.sort(key=lambda item: item[0], reverse=True)
        return [doc for _, doc in ranked[: self.hybrid_top_k]]

    def _should_insert_chunk(self, chunk: dict[str, Any]) -> bool:
        similarity_threshold = float(os.getenv("COSINE_SIMILARITY_THRESHOLD", "0.85"))
        assert self.text_embedder is not None
        assert self.vector_retriever is not None
        query_embedding = self.text_embedder.run(text=chunk["content"])["embedding"]
        result = self.vector_retriever.run(
            query_embedding=query_embedding,
            filters={"field": "meta.record_type", "operator": "==", "value": "knowledge_chunk"},
        )
        docs = result.get("documents") or []
        if not docs:
            return True
        top_doc = docs[0]
        score = getattr(top_doc, "score", None)
        if not isinstance(score, (float, int)):
            return True
        return float(score) < similarity_threshold

    def bootstrap_keyword_store(self, chunks: list[dict[str, Any]]) -> int:
        if not chunks:
            return 0
        docs = self._to_haystack_documents(chunks)
        assert self.keyword_store is not None
        self.keyword_store.write_documents(docs)
        return len(docs)

    def ingest_chunks(self, chunks: list[dict[str, Any]]) -> dict[str, int]:
        if not chunks:
            return {"processed": 0, "inserted": 0}

        dedup_batch_limit = int(os.getenv("DEDUP_BATCH_LIMIT", "30"))
        if len(chunks) > dedup_batch_limit:
            filtered_chunks = chunks
        else:
            filtered_chunks = [chunk for chunk in chunks if self._should_insert_chunk(chunk)]
        if not filtered_chunks:
            return {"processed": len(chunks), "inserted": 0}
        docs = self._to_haystack_documents(filtered_chunks)
        assert self.ingestion_pipeline is not None
        self.ingestion_pipeline.run({"embedder": {"documents": docs}})
        return {"processed": len(chunks), "inserted": len(filtered_chunks)}

    def run_retrieval_pipeline(self, question: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        assert self.text_embedder is not None
        assert self.vector_retriever is not None

        query_embedding = self.text_embedder.run(text=question)["embedding"]
        if not query_embedding:
            return (
                {
                    "answer": "данных недостаточно",
                    "confidence": "low",
                    "needs_review": True,
                    "sources": [],
                },
                [],
            )

        retrieval_result = self.vector_retriever.run(
            query_embedding=query_embedding,
            filters={"field": "meta.record_type", "operator": "==", "value": "knowledge_chunk"},
        )

        retrieved_docs = retrieval_result.get("documents") or []
        context_docs = [
            {"content": doc.content, "meta": doc.meta or {}}
            for doc in retrieved_docs[: self.vector_top_k]
        ]
        if not context_docs:
            return (
                {
                    "answer": "данных недостаточно",
                    "confidence": "low",
                    "needs_review": True,
                    "sources": [],
                },
                [],
            )

        llm_response = generate_answer_from_context(question=question, context_docs=context_docs)

        filtered_sources: list[dict[str, Any]] = []
        for source in llm_response.sources:
            meta = self._find_source_meta(source.quote, context_docs)
            if meta is None:
                continue
            filtered_sources.append(
                {
                    "document_id": meta.get("document_id") or meta.get("filename"),
                    "quote": source.quote,
                    "filename": meta.get("filename"),
                    "chunk_index": meta.get("chunk_index"),
                    "page_number": meta.get("page_number"),
                }
            )

        needs_review = (
            llm_response.needs_review
            or llm_response.confidence == "low"
            or len(filtered_sources) == 0
        )

        return (
            {
                "answer": llm_response.answer,
                "confidence": llm_response.confidence,
                "needs_review": needs_review,
                "sources": filtered_sources,
            },
            context_docs,
        )

    def answer(self, question: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        return self.run_retrieval_pipeline(question)

    def architecture_snapshot(self) -> dict[str, Any]:
        return {
            "sqlite": {
                "documents_table": "documents",
                "qa_runs_table": "qa_runs",
                "audit_runs_table": "audit_runs",
            },
            "vector_store": "pinecone",
            "keyword_store": "haystack_inmemory_bm25",
            "embeddings_provider": "openai",
            "llm_provider": "openai",
            "backend": "fastapi",
            "frontend": "react",
            "hybrid_weights": {"vector": 0.65, "keyword": 0.35, "overlap_bonus": 0.1},
        }

    def clear_knowledge_chunks(self) -> dict[str, int]:
        deleted = {"pinecone": 0, "keyword": 0}

        assert self.pinecone_store is not None
        assert self.keyword_store is not None

        pinecone_docs = self.pinecone_store.filter_documents(
            filters={"field": "meta.record_type", "operator": "==", "value": "knowledge_chunk"}
        )
        pinecone_ids = [str(doc.id) for doc in pinecone_docs if doc.id is not None]
        if pinecone_ids:
            self.pinecone_store.delete_documents(document_ids=pinecone_ids)
            deleted["pinecone"] = len(pinecone_ids)

        keyword_docs = self.keyword_store.filter_documents(
            filters={"field": "meta.record_type", "operator": "==", "value": "knowledge_chunk"}
        )
        keyword_ids = [str(doc.id) for doc in keyword_docs if doc.id is not None]
        if keyword_ids:
            self.keyword_store.delete_documents(document_ids=keyword_ids)
            deleted["keyword"] = len(keyword_ids)

        return deleted

