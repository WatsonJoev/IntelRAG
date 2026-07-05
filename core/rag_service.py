"""
Shared RAG orchestration: cache lookup -> retrieve -> LLM (tier routing + fallback)
-> confidence -> cache store -> audit log.

Extracted so multiple front-ends (Streamlit `app/`, FastAPI `web/`) share one flow.
Returns plain dicts so any view layer can render them.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any

from config.logging_config import get_logger
from config.settings import get_settings
from core.audit import log_query
from core.cache.cache_manager import CacheManager
from core.complexity_classifier import Tier, classify
from core.confidence import score_confidence
from core.llm_service import LLMUnavailableError, call_llm
from core.prompt_builder import build_messages
from core.retriever import retrieve_chunks
from core.schemas import QueryResult
from core.storage.vector_store import VectorStore
from models.db import Document
from models.session import get_db

logger = get_logger(__name__)

NO_CONTEXT_ANSWER = (
    "I don't have enough information in the indexed documents to answer this."
)


def compute_doc_set_hash() -> str:
    """SHA-256 fingerprint of all currently indexed documents (for cache keys)."""
    with get_db() as db:
        docs = db.query(Document).filter(Document.status == "indexed").all()
        parts = sorted(f"{d.id}:{d.created_at.isoformat()}" for d in docs)
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _sources_to_dicts(sources: list) -> list[dict[str, Any]]:
    return [
        {
            "doc_name": c.doc_name,
            "page": c.page_number,
            "text": c.text,
            "score": c.score,
        }
        for c in sources
    ]


def answer_query(
    query: str,
    *,
    session_id: str,
    history: list | None = None,
    vector_store: VectorStore,
    cache_mgr: CacheManager,
    turn_count: int = 0,
) -> dict[str, Any]:
    """
    Run the full RAG loop for a single user query and return a render-ready dict:

        answer, sources, cache, tier, model, model_short, confidence,
        fallback, cost_usd, tokens_in, tokens_out, latency_ms
    """
    s = get_settings()
    history = history or []
    t0 = time.time()

    tier, _ = classify(query, turn_count=turn_count)
    doc_set_hash = compute_doc_set_hash()

    # --- Tier 1 + Tier 2 cache ---
    cached = cache_mgr.lookup(query, doc_set_hash, tier.value)
    if cached:
        badge = "T1 Cache Hit" if cached.cache_tier_hit == "TIER_1" else "T2 Semantic Hit"
        latency_ms = int((time.time() - t0) * 1000)
        log_query(
            session_id=session_id,
            query_text=query,
            model_used=cached.model_used,
            model_tier=cached.model_tier,
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            latency_ms=latency_ms,
            cache_tier_hit=cached.cache_tier_hit,
            confidence=cached.confidence,
            chunks_retrieved=cached.chunks_retrieved,
        )
        return {
            "answer": cached.answer,
            "sources": _sources_to_dicts(cached.sources),
            "cache": badge,
            "tier": cached.model_tier,
            "model": cached.model_used,
            "model_short": cached.model_used.split("/")[-1],
            "confidence": cached.confidence,
            "fallback": cached.fallback_tier,
            "cost_usd": 0.0,
            "tokens_in": 0,
            "tokens_out": 0,
            "latency_ms": latency_ms,
        }

    # --- Retrieval ---
    chunks = retrieve_chunks(query, vector_store, cache_mgr)
    if not chunks:
        latency_ms = int((time.time() - t0) * 1000)
        log_query(
            session_id=session_id,
            query_text=query,
            model_used="-",
            model_tier=tier.value,
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            latency_ms=latency_ms,
            cache_tier_hit=None,
            confidence="LOW",
            chunks_retrieved=0,
        )
        return {
            "answer": NO_CONTEXT_ANSWER,
            "sources": [],
            "cache": "Fresh",
            "tier": tier.value,
            "model": "-",
            "model_short": "-",
            "confidence": "LOW",
            "fallback": None,
            "cost_usd": 0.0,
            "tokens_in": 0,
            "tokens_out": 0,
            "latency_ms": latency_ms,
        }

    messages = build_messages(query, chunks, history=history)

    fallback_chain = [
        (Tier.SIMPLE, s.tier_1_model),
        (Tier.MODERATE, s.tier_2_model),
        (Tier.COMPLEX, s.tier_3_model),
    ]
    start_idx = next(i for i, (t, _) in enumerate(fallback_chain) if t == tier)

    answer: str | None = None
    tokens_in = tokens_out = 0
    cost = 0.0
    fallback_tier: str | None = None
    model_id = "-"

    for fb_tier, fb_model in fallback_chain[start_idx:]:
        try:
            answer, tokens_in, tokens_out, cost = call_llm(messages, fb_model)
            model_id = fb_model
            if fb_tier != tier:
                fallback_tier = fb_tier.value
            break
        except LLMUnavailableError:
            continue

    if answer is None:
        raise LLMUnavailableError("All tiers exhausted")

    confidence = score_confidence(chunks)
    latency_ms = int((time.time() - t0) * 1000)

    result_obj = QueryResult(
        answer=answer,
        sources=chunks,
        model_used=model_id,
        model_tier=tier.value,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost,
        latency_ms=latency_ms,
        cache_tier_hit=None,
        confidence=confidence,
        fallback_tier=fallback_tier,
    )
    cache_mgr.store(query, doc_set_hash, tier.value, result_obj)

    log_query(
        session_id=session_id,
        query_text=query,
        model_used=model_id,
        model_tier=tier.value,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost,
        latency_ms=latency_ms,
        cache_tier_hit=None,
        confidence=confidence,
        chunks_retrieved=len(chunks),
        fallback_tier=fallback_tier,
    )

    return {
        "answer": answer,
        "sources": _sources_to_dicts(chunks),
        "cache": "Fresh",
        "tier": tier.value,
        "model": model_id,
        "model_short": model_id.split("/")[-1],
        "confidence": confidence,
        "fallback": fallback_tier,
        "cost_usd": cost,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "latency_ms": latency_ms,
    }
