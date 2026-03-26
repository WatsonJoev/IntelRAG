"""Confidence scoring: retrieval signals -> LOW / MEDIUM / HIGH label."""
from __future__ import annotations

from core.schemas import RetrievedChunk


def score_confidence(chunks: list) -> str:
    """
    HIGH:   avg similarity >= 0.80 AND chunk count >= 3
    MEDIUM: avg similarity >= 0.65 OR chunk count >= 2
    LOW:    otherwise (single weak chunk or no chunks)
    """
    if not chunks:
        return "LOW"
    avg = sum(c.score for c in chunks) / len(chunks)
    if avg >= 0.80 and len(chunks) >= 3:
        return "HIGH"
    if avg >= 0.65 or len(chunks) >= 2:
        return "MEDIUM"
    return "LOW"
