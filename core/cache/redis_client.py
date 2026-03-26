"""
Redis client wrapper. Uses fakeredis in dev/test; real Redis in production.
"""
from __future__ import annotations

import fakeredis
import redis as redis_lib
from config.settings import get_settings

_client = None


def get_redis():
    global _client
    if _client is None:
        s = get_settings()
        use_real = (
            s.redis_url
            and s.redis_url.startswith("redis://")
            and s.environment not in ("development", "test")
        )
        if use_real:
            _client = redis_lib.from_url(s.redis_url, decode_responses=False)
        else:
            _client = fakeredis.FakeRedis()
    return _client


def reset_client() -> None:
    """Force re-initialisation (useful in tests)."""
    global _client
    _client = None
