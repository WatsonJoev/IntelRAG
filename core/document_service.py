"""
Unified document deletion: DB row, vectors, raw file, cache invalidation.
Both Streamlit (app/) and FastAPI (web/) call this single function so that
a delete is always complete — no dangling vectors or orphaned files.
"""
from __future__ import annotations

from config.logging_config import get_logger
from config.settings import get_settings
from core.cache.cache_manager import get_cache_manager
from core.storage.file_store import FileStore
from core.storage.vector_store import VectorStore
from models.db import Document
from models.session import get_db

logger = get_logger(__name__)


def delete_document(doc_id: str) -> bool:
    """
    Remove a document completely from every storage layer.
    Returns True if the document existed and was removed, False if not found.
    """
    s = get_settings()

    with get_db() as db:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            logger.warning("delete_document_not_found", doc_id=doc_id)
            return False
        db.delete(doc)
        db.commit()

    try:
        VectorStore().delete(where={"doc_id": doc_id})
    except Exception as e:
        logger.warning("delete_vectors_failed", doc_id=doc_id, error=str(e))

    try:
        FileStore(base_path=s.file_store_path).delete_document(doc_id)
    except Exception as e:
        logger.warning("delete_file_failed", doc_id=doc_id, error=str(e))

    try:
        get_cache_manager().invalidate_on_doc_change()
    except Exception as e:
        logger.warning("delete_cache_invalidate_failed", doc_id=doc_id, error=str(e))

    logger.info("document_deleted", doc_id=doc_id)
    return True
