"""RAG retriever: embed query -> vector search -> filter -> deduplicate -> assemble context."""
from __future__ import annotations

from typing import Optional

from core.embedding_service import embed_texts
from core.schemas import RetrievedChunk
from config.settings import get_settings


def retrieve_chunks(
    query: str,
    vector_store,
    cache_manager,
    top_k: Optional[int] = None,
    top_k_rerank: Optional[int] = None,
    threshold: Optional[float] = None,
) -> list:
    """
    1. Get query embedding (Tier 3 cache -> compute if miss)
    2. Search vector store top_k candidates
    3. Convert ChromaDB distances to similarity scores (sim = 1 - dist)
    4. Filter below threshold
    5. Deduplicate adjacent chunks from same doc
    6. Return top_k_rerank results ordered by score desc
    """
    settings = get_settings()
    top_k = top_k or settings.top_k_retrieval
    top_k_rerank = top_k_rerank or settings.top_k_rerank
    threshold = threshold if threshold is not None else settings.similarity_threshold

    # Tier 3 embedding cache
    embedding = cache_manager.get_embedding(query, settings.embedding_model)
    if embedding is None:
        embedding = embed_texts([query])[0]
        cache_manager.store_embedding(query, settings.embedding_model, embedding)

    count = vector_store.count()
    if count == 0:
        return []

    results = vector_store.search(
        query_embeddings=[embedding],
        n_results=min(top_k, count),
    )

    ids = results.get("ids", [[]])[0]
    distances = results.get("distances", [[]])[0]
    texts = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    chunks = []
    for i, (dist, text, meta) in enumerate(zip(distances, texts, metadatas)):
        similarity = 1.0 - float(dist)  # ChromaDB cosine distance -> similarity
        if similarity < threshold:
            continue
        chunks.append(
            RetrievedChunk(
                text=text or "",
                doc_name=meta.get("source_file", "unknown"),
                page_number=int(meta.get("page_number", 0)) or None,
                chunk_index=int(meta.get("chunk_index", i)),
                score=round(similarity, 4),
            )
        )

    chunks = _deduplicate(chunks)
    chunks.sort(key=lambda c: c.score, reverse=True)
    return chunks[:top_k_rerank]


def _deduplicate(chunks: list) -> list:
    """Remove chunks adjacent to a higher-scoring chunk from the same doc."""
    seen = set()
    result = []
    for chunk in sorted(chunks, key=lambda c: c.score, reverse=True):
        key = (chunk.doc_name, chunk.chunk_index)
        adjacent = (
            (chunk.doc_name, chunk.chunk_index - 1) in seen
            or (chunk.doc_name, chunk.chunk_index + 1) in seen
        )
        if not adjacent:
            result.append(chunk)
            seen.add(key)
    return result
