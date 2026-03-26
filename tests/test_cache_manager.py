import pytest
from core.cache.cache_manager import CacheManager
from core.cache.redis_client import reset_client
from core.schemas import QueryResult, RetrievedChunk


@pytest.fixture(autouse=True)
def fresh_redis():
    reset_client()
    import core.cache.cache_manager as cm_module
    cm_module._manager = None
    yield
    reset_client()
    cm_module._manager = None


def _result(answer: str = "test answer") -> QueryResult:
    chunk = RetrievedChunk(text="ctx", doc_name="doc.pdf", page_number=1, chunk_index=0, score=0.9)
    return QueryResult(
        answer=answer, sources=[chunk],
        model_used="meta-llama/llama-3.1-8b-instruct:free",
        model_tier="SIMPLE", tokens_in=50, tokens_out=30,
        cost_usd=0.0, latency_ms=500,
        cache_tier_hit=None, confidence="HIGH",
    )


def test_tier1_miss_then_hit():
    cm = CacheManager()
    result = cm.lookup("what is X?", "hash1", "model-a")
    assert result is None

    cm.store("what is X?", "hash1", "model-a", _result())
    hit = cm.lookup("what is X?", "hash1", "model-a")
    assert hit is not None
    assert hit.cache_tier_hit == "TIER_1"


def test_tier1_different_doc_hash_miss():
    cm = CacheManager()
    cm.store("what is X?", "hash1", "model-a", _result())
    result = cm.lookup("what is X?", "hash2", "model-a")
    assert result is None


def test_tier3_store_and_retrieve():
    cm = CacheManager()
    emb = [0.1] * 384
    cm.store_embedding("hello world", "model-v1", emb)
    retrieved = cm.get_embedding("hello world", "model-v1")
    assert retrieved is not None
    assert len(retrieved) == 384
    assert abs(retrieved[0] - 0.1) < 0.001


def test_tier3_miss_returns_none():
    cm = CacheManager()
    result = cm.get_embedding("nonexistent text", "model-v1")
    assert result is None


def test_invalidation_clears_tier1():
    cm = CacheManager()
    cm.store("query", "hash1", "model-a", _result())
    cm.invalidate_on_doc_change()
    result = cm.lookup("query", "hash1", "model-a")
    assert result is None


def test_stats_track_hits():
    cm = CacheManager()
    cm.store("q", "h", "m", _result())
    cm.lookup("q", "h", "m")
    cm.lookup("other", "h", "m")
    stats = cm.get_stats()
    assert stats["tier1_hits"] >= 1
    assert stats["misses"] >= 1
