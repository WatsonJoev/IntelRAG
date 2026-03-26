def test_cache_manager_stub_lookup_returns_none():
    from core.cache.cache_manager import get_cache_manager
    cm = get_cache_manager()
    assert cm.lookup("any query", "any_hash", "any_model") is None


def test_cache_manager_stub_get_embedding_returns_none():
    from core.cache.cache_manager import get_cache_manager
    cm = get_cache_manager()
    assert cm.get_embedding("text", "model") is None
