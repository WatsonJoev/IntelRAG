"""Shared dataclasses used across the RAG pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RetrievedChunk:
    text: str
    doc_name: str
    page_number: Optional[int]
    chunk_index: int
    score: float  # cosine similarity 0-1


@dataclass
class QueryResult:
    answer: str
    sources: list
    model_used: str
    model_tier: str        # "SIMPLE" | "MODERATE" | "COMPLEX"
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    cache_tier_hit: Optional[str]   # "TIER_1" | "TIER_2" | None
    confidence: str        # "LOW" | "MEDIUM" | "HIGH"
    fallback_tier: Optional[str] = None
    chunks_retrieved: int = field(init=False)

    def __post_init__(self) -> None:
        self.chunks_retrieved = len(self.sources)
