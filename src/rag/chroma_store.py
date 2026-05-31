"""ChromaDB wrapper with category-based filtering and source attribution."""
from __future__ import annotations

from typing import Any

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)

CATEGORIES = ("investing", "portfolio", "tax", "goals", "market")


class Document:
    def __init__(
        self,
        content: str,
        metadata: dict[str, Any],
        doc_id: str | None = None,
    ) -> None:
        self.content = content
        self.metadata = metadata
        self.doc_id = doc_id or metadata.get("doc_id", "")


class ChromaStore:
    def __init__(self) -> None:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        try:
            # Connect to remote Chroma service (docker-compose)
            self._client = chromadb.HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        except Exception:
            # Fallback: local persistent client
            self._client = chromadb.PersistentClient(
                path=settings.chroma_persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )

        self._col = self._client.get_or_create_collection(
            name="finance_kb",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("chroma connected", collection="finance_kb", count=self._col.count())

    def add_documents(self, docs: list[Document]) -> None:
        if not docs:
            return
        ids = [d.doc_id for d in docs]
        texts = [d.content for d in docs]
        metas = [d.metadata for d in docs]
        self._col.upsert(ids=ids, documents=texts, metadatas=metas)
        logger.info("chroma upserted", count=len(docs))

    def query(
        self,
        text: str,
        categories: list[str] | None = None,
        k: int = 5,
    ) -> list[Document]:
        where: dict | None = None
        if categories:
            valid = [c for c in categories if c in CATEGORIES]
            if valid:
                if len(valid) == 1:
                    where = {"category": valid[0]}
                else:
                    where = {"category": {"$in": valid}}

        try:
            result = self._col.query(
                query_texts=[text],
                n_results=min(k, self._col.count() or 1),
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            logger.warning("chroma query failed", error=str(exc))
            return []

        docs: list[Document] = []
        for content, meta in zip(
            result["documents"][0], result["metadatas"][0]
        ):
            docs.append(Document(content=content, metadata=meta, doc_id=meta.get("doc_id", "")))
        return docs

    def count(self) -> int:
        return self._col.count()
