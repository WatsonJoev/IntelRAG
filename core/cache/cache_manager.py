"""
3-tier cache manager using fakeredis (swappable to real Redis).

Tier 1: Exact-match — Redis STRING, key=SHA-256(query+corpus+model), TTL=24h
Tier 2: Semantic    — Redis HASH per entry + SET index, cosine scan, TTL=48h
Tier 3: Embedding   — Redis STRING (binary), key=SHA-256(text+model), no TTL
"""
from __future__ import annotations

import hashlib
import json
import struct
import uuid
from typing import Optional

import numpy as np

from config.logging_config import get_logger
from config.settings import get_settings
from core.cache.redis_client import get_redis
from core.schemas import QueryResult, RetrievedChunk

logger = get_logger(__name__)

_T1 = "cache:exact:"
_T2 = "cache:semantic:"
_T2I = "cache:semantic:index"
_T3 = "cache:embedding:"
_STATS = "stats:"


def _sha256(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _encode_embedding(emb: list) -> bytes:
    return struct.pack(f"{len(emb)}f", *emb)


def _decode_embedding(data: bytes) -> list:
    n = len(data) // 4
    return list(struct.unpack(f"{n}f", data))


def _cosine(a: list, b: list) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(np.dot(va, vb) / denom) if denom > 0 else 0.0


def _result_to_json(result: QueryResult) -> str:
    d = {
        "answer": result.answer,
        "sources": [
            {"text": s.text, "doc_name": s.doc_name, "page_number": s.page_number,
             "chunk_index": s.chunk_index, "score": s.score}
            for s in result.sources
        ],
        "model_used": result.model_used,
        "model_tier": result.model_tier,
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
        "cost_usd": result.cost_usd,
        "latency_ms": result.latency_ms,
        "confidence": result.confidence,
        "fallback_tier": result.fallback_tier,
    }
    return json.dumps(d)


def _json_to_result(data: str, cache_tier: str) -> QueryResult:
    d = json.loads(data)
    sources = [
        RetrievedChunk(
            text=s["text"], doc_name=s["doc_name"],
            page_number=s["page_number"], chunk_index=s["chunk_index"], score=s["score"],
        )
        for s in d["sources"]
    ]
    return QueryResult(
        answer=d["answer"], sources=sources,
        model_used=d["model_used"], model_tier=d["model_tier"],
        tokens_in=d["tokens_in"], tokens_out=d["tokens_out"],
        cost_usd=d["cost_usd"], latency_ms=d["latency_ms"],
        cache_tier_hit=cache_tier, confidence=d["confidence"],
        fallback_tier=d.get("fallback_tier"),
    )


class CacheManager:

    def lookup(self, query: str, doc_set_hash: str, model_id: str) -> Optional[QueryResult]:
        r = get_redis()
        s = get_settings()

        t1_key = _T1 + _sha256(query, doc_set_hash, model_id)
        raw = r.get(t1_key)
        if raw:
            r.incr(_STATS + "tier1_hits")
            logger.debug("cache_tier1_hit", key=t1_key[:20])
            return _json_to_result(raw.decode(), "TIER_1")

        index_key = _T2I + ":" + doc_set_hash
        index_members = r.smembers(index_key)
        if index_members:
            query_emb = self.get_embedding(query, s.embedding_model)
            if query_emb is None:
                from core.embedding_service import embed_texts
                query_emb = embed_texts([query])[0]
            best_score = 0.0
            best_response = None
            for member in index_members:
                entry_key = _T2 + member.decode()
                if not r.exists(entry_key):
                    r.srem(index_key, member)
                    continue
                stored_emb_bytes = r.hget(entry_key, "embedding")
                if not stored_emb_bytes:
                    continue
                stored_emb = _decode_embedding(stored_emb_bytes)
                sim = _cosine(query_emb, stored_emb)
                if sim > best_score:
                    best_score = sim
                    best_response = r.hget(entry_key, "response")
                    if best_response:
                        best_response = best_response.decode()
            if best_score >= s.cache_semantic_similarity_threshold and best_response:
                r.incr(_STATS + "tier2_hits")
                logger.debug("cache_tier2_hit", similarity=round(best_score, 3))
                return _json_to_result(best_response, "TIER_2")

        r.incr(_STATS + "misses")
        return None

    def store(self, query: str, doc_set_hash: str, model_id: str, result: QueryResult) -> None:
        r = get_redis()
        s = get_settings()

        t1_key = _T1 + _sha256(query, doc_set_hash, model_id)
        r.set(t1_key, _result_to_json(result), ex=s.cache_exact_ttl)

        emb = self.get_embedding(query, s.embedding_model)
        if emb is None:
            from core.embedding_service import embed_texts
            emb = embed_texts([query])[0]
            self.store_embedding(query, s.embedding_model, emb)
        entry_id = str(uuid.uuid4())
        entry_key = _T2 + entry_id
        r.hset(entry_key, mapping={
            "embedding": _encode_embedding(emb),
            "response": _result_to_json(result),
        })
        r.expire(entry_key, s.cache_semantic_ttl)
        index_key = _T2I + ":" + doc_set_hash
        r.sadd(index_key, entry_id)

    def get_embedding(self, text: str, model_name: str) -> Optional[list]:
        r = get_redis()
        key = _T3 + _sha256(text, model_name)
        raw = r.get(key)
        if raw:
            return _decode_embedding(raw)
        return None

    def store_embedding(self, text: str, model_name: str, embedding: list) -> None:
        r = get_redis()
        key = _T3 + _sha256(text, model_name)
        r.set(key, _encode_embedding(embedding))

    def invalidate_on_doc_change(self) -> None:
        """Flush Tier 1 + Tier 2. Tier 3 (embedding) is preserved."""
        r = get_redis()
        for key in r.scan_iter(_T1 + "*"):
            r.delete(key)
        # Clear all per-doc-set semantic index keys and their entries
        for index_key in r.scan_iter(_T2I + ":*"):
            for member in r.smembers(index_key):
                r.delete(_T2 + member.decode())
            r.delete(index_key)
        logger.info("cache_invalidated", tiers="T1+T2")

    def flush_embedding_cache(self) -> None:
        r = get_redis()
        for key in r.scan_iter(_T3 + "*"):
            r.delete(key)

    def get_stats(self) -> dict:
        r = get_redis()
        def _get(k: str) -> int:
            v = r.get(_STATS + k)
            return int(v) if v else 0
        return {
            "tier1_hits": _get("tier1_hits"),
            "tier2_hits": _get("tier2_hits"),
            "tier3_hits": _get("tier3_hits"),
            "misses": _get("misses"),
        }


_manager = None


def get_cache_manager() -> CacheManager:
    global _manager
    if _manager is None:
        _manager = CacheManager()
    return _manager
