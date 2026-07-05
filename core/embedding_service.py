"""
Embedding service: local sentence-transformers with optional batch processing.
"""
from __future__ import annotations

from typing import Any

from config.logging_config import get_logger
from config.settings import get_settings

logger = get_logger(__name__)

_model: Any = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        s = get_settings()
        _model = SentenceTransformer(s.embedding_model)
        logger.info("embedding_model_loaded", model=s.embedding_model)
    return _model


def embed_texts(texts: list[str], batch_size: int | None = None) -> list[list[float]]:
    """
    Embed a list of texts in batches. Returns list of vectors.
    """
    if not texts:
        return []
    s = get_settings()
    batch_size = batch_size or s.embedding_batch_size
    model = _get_model()
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=len(texts) > 50,
        normalize_embeddings=True,
    )
    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    """Embed a single query string."""
    return embed_texts([query])[0]


def max_sequence_tokens() -> int:
    """Max tokens the embedding model encodes before silently truncating."""
    return int(getattr(_get_model(), "max_seq_length", 256))


def count_tokens(text: str) -> int:
    """Token count for `text` under the embedding model's own tokenizer."""
    tokenizer = _get_model().tokenizer
    return len(tokenizer.encode(text, add_special_tokens=False))
