"""
Vector store abstraction: ChromaDB implementation with HNSW, cosine similarity.
Interface allows swapping to Qdrant via config.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions

from config.logging_config import get_logger
from config.settings import get_settings

logger = get_logger(__name__)


@runtime_checkable
class VectorStoreProtocol(Protocol):
    def add_with_embeddings(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
        documents: list[str] | None = None,
    ) -> None: ...

    def search(
        self,
        query_embeddings: list[list[float]] | None = None,
        query_texts: list[str] | None = None,
        n_results: int = 20,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    def delete(self, ids: list[str] | None = None, where: dict[str, Any] | None = None) -> None: ...

    def count(self) -> int: ...


class VectorStore(VectorStoreProtocol):
    """
    ChromaDB-backed vector store for chunk embeddings.
    Uses HNSW index and cosine similarity.
    """

    def __init__(
        self,
        persist_dir: str | None = None,
        collection_name: str = "intelrag",
        embedding_function: Any = None,
    ) -> None:
        settings = get_settings()
        self.persist_dir = persist_dir or settings.chroma_persist_dir
        self.collection_name = collection_name
        if embedding_function is None:
            self._ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=settings.embedding_model
            )
        else:
            self._ef = embedding_function
        self._client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "vector_store_initialized",
            backend="chromadb",
            collection=collection_name,
            path=self.persist_dir,
        )

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]] | None = None,
        documents: list[str] | None = None,
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """Add or update vectors. If documents given, embeddings are computed."""
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def add_with_embeddings(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
        documents: list[str] | None = None,
    ) -> None:
        """Add precomputed embeddings with metadata."""
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )

    def search(
        self,
        query_embeddings: list[list[float]] | None = None,
        query_texts: list[str] | None = None,
        n_results: int = 20,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Query by embedding or text. Returns ids, distances, metadatas, documents."""
        return self._collection.query(
            query_embeddings=query_embeddings,
            query_texts=query_texts,
            n_results=n_results,
            where=where,
        )

    def delete(self, ids: list[str] | None = None, where: dict[str, Any] | None = None) -> None:
        """Delete by ids or filter."""
        self._collection.delete(ids=ids, where=where)

    def count(self) -> int:
        return self._collection.count()

    def get_embedding_function(self) -> Any:
        return self._ef
