"""
Query complexity classifier: rule-based, ~5ms.
Returns (Tier, model_id_string).
"""
from __future__ import annotations

from enum import Enum

from config.settings import get_settings

COMPLEX_KEYWORDS = {
    "compare", "contrast", "synthesize", "recommend",
    "evaluate", "contradict", "analyze", "assess", "critique",
    "differentiate", "reconcile",
}
MODERATE_KEYWORDS = {
    "summarize", "explain", "describe", "outline",
    "overview", "elaborate", "discuss", "review",
}
SIMPLE_KEYWORDS = {
    "define", "what", "who", "when", "where", "list",
    "name", "how many", "count", "show",
}


class Tier(str, Enum):
    SIMPLE = "SIMPLE"
    MODERATE = "MODERATE"
    COMPLEX = "COMPLEX"


def classify(
    query: str,
    turn_count: int,
    retrieved_doc_count: int = 1,
) -> tuple:
    """Returns (Tier, model_id). Hard keyword signals take priority."""
    s = get_settings()
    tokens = query.lower().split()
    token_set = set(tokens)

    # Conversation depth and doc count override keyword signals
    if turn_count >= 5 or retrieved_doc_count >= 4:
        return Tier.COMPLEX, s.tier_3_model
    if turn_count >= 3 or retrieved_doc_count >= 2:
        return Tier.MODERATE, s.tier_2_model

    if token_set & COMPLEX_KEYWORDS:
        return Tier.COMPLEX, s.tier_3_model
    if token_set & MODERATE_KEYWORDS:
        return Tier.MODERATE, s.tier_2_model
    if token_set & SIMPLE_KEYWORDS and len(tokens) < 20:
        return Tier.SIMPLE, s.tier_1_model

    if len(tokens) < 15:
        return Tier.SIMPLE, s.tier_1_model
    if len(tokens) < 40:
        return Tier.MODERATE, s.tier_2_model
    return Tier.COMPLEX, s.tier_3_model
