"""
Cache manager: 3-tier cache stub.
Sprint 4 implements all tiers. This stub provides the interface so Sprint 2/3 can call it.
"""
from __future__ import annotations

from typing import Optional


class CacheManager:
    """Stub - all methods are no-ops until Sprint 4 fills them in."""

    def lookup(self, query: str, doc_set_hash: str, model_id: str) -> Optional[object]:
        return None

    def store(self, query: str, doc_set_hash: str, model_id: str, result: object) -> None:
        pass

    def get_embedding(self, text: str, model_name: str) -> Optional[list]:
        return None

    def store_embedding(self, text: str, model_name: str, embedding: list) -> None:
        pass

    def invalidate_on_doc_change(self) -> None:
        pass

    def get_stats(self) -> dict:
        return {"tier1_hits": 0, "tier2_hits": 0, "tier3_hits": 0, "misses": 0}


_manager = None


def get_cache_manager() -> CacheManager:
    global _manager
    if _manager is None:
        _manager = CacheManager()
    return _manager
