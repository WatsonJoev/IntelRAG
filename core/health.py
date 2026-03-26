"""Health checks for all storage layers and external services."""
from __future__ import annotations

from config.logging_config import get_logger

logger = get_logger(__name__)


def check_all() -> dict:
    return {
        "vector_store": _ping_chromadb(),
        "metadata_db": _ping_sqlite(),
        "cache": _ping_cache(),
        "openrouter": _ping_openrouter(),
    }


def _ping_chromadb() -> bool:
    try:
        from core.storage.vector_store import VectorStore
        vs = VectorStore()
        vs.count()
        return True
    except Exception as e:
        logger.warning("health_chromadb_fail", error=str(e))
        return False


def _ping_sqlite() -> bool:
    try:
        import sqlalchemy
        from models.session import get_db
        with get_db() as db:
            db.execute(sqlalchemy.text("SELECT 1"))
        return True
    except Exception as e:
        logger.warning("health_sqlite_fail", error=str(e))
        return False


def _ping_cache() -> bool:
    try:
        from core.cache.redis_client import get_redis
        r = get_redis()
        r.ping()
        return True
    except Exception as e:
        logger.warning("health_cache_fail", error=str(e))
        return False


def _ping_openrouter() -> bool:
    try:
        import httpx
        from config.settings import get_settings
        s = get_settings()
        r = httpx.head(s.openrouter_base_url, timeout=3.0)
        return r.status_code < 500
    except Exception as e:
        logger.warning("health_openrouter_fail", error=str(e))
        return False
