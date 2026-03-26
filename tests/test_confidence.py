from core.schemas import RetrievedChunk
from core.confidence import score_confidence


def _chunk(s: float) -> RetrievedChunk:
    return RetrievedChunk(text="t", doc_name="d", page_number=1, chunk_index=0, score=s)


def test_high_confidence():
    chunks = [_chunk(0.85), _chunk(0.90), _chunk(0.82)]
    assert score_confidence(chunks) == "HIGH"


def test_medium_confidence_by_score():
    chunks = [_chunk(0.70), _chunk(0.68)]
    assert score_confidence(chunks) == "MEDIUM"


def test_medium_confidence_by_count():
    chunks = [_chunk(0.60), _chunk(0.61)]
    assert score_confidence(chunks) == "MEDIUM"


def test_low_confidence_single_weak_chunk():
    chunks = [_chunk(0.55)]
    assert score_confidence(chunks) == "LOW"


def test_low_confidence_empty():
    assert score_confidence([]) == "LOW"
