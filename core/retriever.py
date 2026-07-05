"""RAG retriever: embed query -> vector search -> hybrid re-rank -> filter -> deduplicate."""
from __future__ import annotations

import re

from config.settings import get_settings
from core.embedding_service import embed_texts
from core.schemas import RetrievedChunk

# Dense embeddings under-rank exact keyword / proper-noun matches (e.g. names on a
# résumé). Hybrid search adds a lexical signal so those chunks are not dropped.
_WORD_RE = re.compile(r"[a-z0-9]+")
_LEXICAL_WEIGHT = 0.4  # how much a full lexical match can boost a dense score
_STOPWORDS = {
    "the", "and", "are", "for", "was", "were", "with", "that", "this", "from",
    "who", "what", "when", "where", "which", "why", "how", "does", "did", "has",
    "have", "had", "is", "in", "on", "of", "to", "a", "an", "it", "its", "be",
    "or", "as", "at", "by", "he", "she", "his", "her", "they", "them", "you",
    "working", "work", "somewhere", "someone", "anything", "something",
}


def _content_terms(query: str) -> list[str]:
    """Meaningful query terms (drop stopwords / very short tokens) for lexical match."""
    return [t for t in _WORD_RE.findall(query.lower()) if len(t) >= 3 and t not in _STOPWORDS]


def retrieve_chunks(
    query: str,
    vector_store,
    cache_manager,
    top_k: int | None = None,
    top_k_rerank: int | None = None,
    threshold: float | None = None,
) -> list:
    """
    1. Get query embedding (Tier 3 cache -> compute if miss)
    2. Search vector store top_k candidates
    3. Convert ChromaDB distances to similarity scores (sim = 1 - dist)
    4. Hybrid re-rank: blend dense similarity with lexical keyword overlap
    5. Keep chunks above threshold OR with a lexical match, then deduplicate
    6. Return top_k_rerank results ordered by combined relevance
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

    distances = results.get("distances", [[]])[0]
    texts = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    terms = _content_terms(query) if settings.hybrid_search else []

    scored: list[tuple[float, RetrievedChunk]] = []
    for i, (dist, text, meta) in enumerate(zip(distances, texts, metadatas, strict=False)):
        dense = 1.0 - float(dist)  # ChromaDB cosine distance -> similarity

        if terms:
            # Match query terms against the chunk text AND its source filename, so a
            # name query (e.g. "manikandan venu") surfaces every chunk of that
            # person's document -- not just the one chunk that repeats the name.
            words = set(_WORD_RE.findall((text or "").lower()))
            words |= set(_WORD_RE.findall(str(meta.get("source_file", "")).lower()))
            hits = sum(1 for t in terms if t in words)
            combined = dense + _LEXICAL_WEIGHT * (hits / len(terms))
            # Never drop a chunk that lexically matches the query (recall for names).
            keep = combined >= threshold or hits > 0
        else:
            hits = 0
            combined = dense
            keep = dense >= threshold

        if not keep:
            continue

        chunk = RetrievedChunk(
            text=text or "",
            doc_name=meta.get("source_file", "unknown"),
            page_number=int(meta.get("page_number", 0)) or None,
            chunk_index=int(meta.get("chunk_index", i)),
            score=round(dense, 4),  # displayed score stays the honest dense similarity
        )
        scored.append((combined, chunk))

    # Rank by combined relevance and take the strongest chunks, then widen each
    # with its neighbours so split information (e.g. an employer name spanning two
    # chunks) is reassembled for the LLM.
    scored.sort(key=lambda pair: pair[0], reverse=True)
    ranked = _dedupe_exact(chunk for _, chunk in scored)
    primaries = ranked[:top_k_rerank]
    return _expand_neighbors(primaries, [chunk for _, chunk in scored])


def _dedupe_exact(chunks) -> list:
    """Drop exact-duplicate chunks (same doc + index), preserving order."""
    seen = set()
    result = []
    for chunk in chunks:
        key = (chunk.doc_name, chunk.chunk_index)
        if key not in seen:
            seen.add(key)
            result.append(chunk)
    return result


def _expand_neighbors(primaries: list, candidates: list) -> list:
    """Add each primary chunk's immediate neighbours (idx +/-1) from the retrieved
    candidate pool, preserving reading order within a document. Neighbours must
    themselves have survived retrieval filtering (they are in `candidates`)."""
    pool = {(c.doc_name, c.chunk_index): c for c in candidates}
    result: list = []
    used: set = set()
    for chunk in primaries:
        for idx in (chunk.chunk_index - 1, chunk.chunk_index, chunk.chunk_index + 1):
            key = (chunk.doc_name, idx)
            neighbor = pool.get(key)
            if neighbor is not None and key not in used:
                used.add(key)
                result.append(neighbor)
    return result
