from core.schemas import RetrievedChunk, QueryResult


def test_retrieved_chunk_fields():
    chunk = RetrievedChunk(
        text="Sample text",
        doc_name="report.pdf",
        page_number=3,
        chunk_index=0,
        score=0.85,
    )
    assert chunk.score == 0.85
    assert chunk.doc_name == "report.pdf"


def test_query_result_cache_none_by_default():
    chunk = RetrievedChunk(text="t", doc_name="d", page_number=1, chunk_index=0, score=0.8)
    result = QueryResult(
        answer="The answer",
        sources=[chunk],
        model_used="meta-llama/llama-3.1-8b-instruct:free",
        model_tier="SIMPLE",
        tokens_in=100,
        tokens_out=50,
        cost_usd=0.0,
        latency_ms=1200,
        cache_tier_hit=None,
        confidence="HIGH",
        fallback_tier=None,
    )
    assert result.cache_tier_hit is None
    assert len(result.sources) == 1
