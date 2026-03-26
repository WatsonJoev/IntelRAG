"""Audit log helpers: write QueryLog, TokenUsage, IngestionLog rows."""
from __future__ import annotations

from datetime import date
from typing import Optional

from config.logging_config import get_logger
from models.db import IngestionLog, QueryLog, TokenUsage
from models.session import get_db

logger = get_logger(__name__)

TIER_COLUMN = {
    "SIMPLE": ("tier_1_tokens", "tier_1_cost"),
    "MODERATE": ("tier_2_tokens", "tier_2_cost"),
    "COMPLEX": ("tier_3_tokens", "tier_3_cost"),
}


def log_query(
    session_id: str,
    query_text: str,
    model_used: str,
    model_tier: str,
    tokens_in: int,
    tokens_out: int,
    cost_usd: float,
    latency_ms: int,
    cache_tier_hit: Optional[str],
    confidence: str,
    chunks_retrieved: int,
    fallback_tier: Optional[str] = None,
) -> None:
    try:
        with get_db() as db:
            row = QueryLog(
                session_id=session_id,
                query_text=query_text[:2000],
                model_used=model_used,
                model_tier=model_tier,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                cache_tier_hit=cache_tier_hit,
                confidence=confidence,
                chunks_retrieved=chunks_retrieved,
                fallback_tier=fallback_tier,
            )
            db.add(row)
            db.commit()
        _upsert_token_usage(model_tier, tokens_in + tokens_out, cost_usd)
    except Exception as e:
        logger.warning("audit_log_failed", error=str(e))


def _upsert_token_usage(tier: str, total_tokens: int, cost: float) -> None:
    tok_col, cost_col = TIER_COLUMN.get(tier, ("tier_1_tokens", "tier_1_cost"))
    today = date.today()
    try:
        with get_db() as db:
            row = db.query(TokenUsage).filter(TokenUsage.date == today).first()
            if row:
                setattr(row, tok_col, getattr(row, tok_col) + total_tokens)
                setattr(row, cost_col, getattr(row, cost_col) + cost)
                row.total_cost = row.tier_1_cost + row.tier_2_cost + row.tier_3_cost
            else:
                kwargs = {tok_col: total_tokens, cost_col: cost, "total_cost": cost}
                row = TokenUsage(date=today, **kwargs)
                db.add(row)
            db.commit()
    except Exception as e:
        logger.warning("token_usage_upsert_failed", error=str(e))


def log_ingestion(
    document_id: str,
    status: str,
    chunks_created: int = 0,
    duration_ms: int = 0,
    error_message: Optional[str] = None,
) -> None:
    try:
        with get_db() as db:
            row = IngestionLog(
                document_id=document_id,
                status=status,
                chunks_created=chunks_created,
                duration_ms=duration_ms,
                error_message=error_message,
            )
            db.add(row)
            db.commit()
    except Exception as e:
        logger.warning("ingestion_log_failed", error=str(e))
