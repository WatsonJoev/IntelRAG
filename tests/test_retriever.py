from unittest.mock import MagicMock, patch

from core.retriever import retrieve_chunks
from core.schemas import RetrievedChunk


def _make_chroma_response(scores, texts, metadatas):
    return {
        "ids": [[f"id_{i}" for i in range(len(scores))]],
        "distances": [scores],
        "documents": [texts],
        "metadatas": [metadatas],
    }


def test_retrieve_filters_below_threshold():
    mock_vs = MagicMock()
    mock_vs.count.return_value = 3
    mock_vs.search.return_value = _make_chroma_response(
        scores=[0.3, 0.8, 0.6],
        texts=["low sim", "high sim", "medium sim"],
        metadatas=[
            {"doc_id": "d1", "source_file": "a.pdf", "page_number": 1, "chunk_index": 0},
            {"doc_id": "d1", "source_file": "a.pdf", "page_number": 2, "chunk_index": 1},
            {"doc_id": "d1", "source_file": "a.pdf", "page_number": 3, "chunk_index": 2},
        ],
    )
    mock_cache = MagicMock()
    mock_cache.get_embedding.return_value = None
    mock_embed = MagicMock(return_value=[[0.1] * 384])

    # Explicit threshold so the test is deterministic regardless of config.
    # distances [0.3, 0.8, 0.6] -> similarities [0.7, 0.2, 0.4]; only 0.7 passes.
    with patch("core.retriever.embed_texts", mock_embed):
        chunks = retrieve_chunks("test query", mock_vs, mock_cache, threshold=0.7)

    assert chunks  # at least one survives the filter
    assert all(c.score >= 0.7 for c in chunks)


def test_retrieve_returns_retrieved_chunks():
    mock_vs = MagicMock()
    mock_vs.count.return_value = 2
    mock_vs.search.return_value = _make_chroma_response(
        scores=[0.1, 0.15],
        texts=["First chunk", "Second chunk"],
        metadatas=[
            {"doc_id": "d1", "source_file": "doc.pdf", "page_number": 1, "chunk_index": 0},
            {"doc_id": "d1", "source_file": "doc.pdf", "page_number": 2, "chunk_index": 1},
        ],
    )
    mock_cache = MagicMock()
    mock_cache.get_embedding.return_value = None
    mock_embed = MagicMock(return_value=[[0.1] * 384])

    with patch("core.retriever.embed_texts", mock_embed):
        chunks = retrieve_chunks("query", mock_vs, mock_cache)

    assert len(chunks) >= 1
    assert isinstance(chunks[0], RetrievedChunk)


def test_retrieve_empty_collection_returns_empty():
    mock_vs = MagicMock()
    mock_vs.count.return_value = 0
    mock_cache = MagicMock()
    mock_cache.get_embedding.return_value = None
    mock_embed = MagicMock(return_value=[[0.1] * 384])

    with patch("core.retriever.embed_texts", mock_embed):
        chunks = retrieve_chunks("query", mock_vs, mock_cache)

    assert chunks == []


def test_hybrid_keeps_below_threshold_lexical_match():
    # A chunk whose dense similarity is below threshold but that lexically matches
    # a query term (e.g. a name) must still be retrieved.
    mock_vs = MagicMock()
    mock_vs.count.return_value = 2
    mock_vs.search.return_value = _make_chroma_response(
        scores=[0.85, 0.30],  # distances -> sims 0.15 (below thr) and 0.70
        texts=["Manikandan Venu, Senior Data Engineer", "unrelated policy text"],
        metadatas=[
            {"source_file": "resume.pdf", "page_number": 1, "chunk_index": 0},
            {"source_file": "policy.pdf", "page_number": 1, "chunk_index": 0},
        ],
    )
    mock_cache = MagicMock()
    mock_cache.get_embedding.return_value = None
    mock_embed = MagicMock(return_value=[[0.1] * 384])

    with patch("core.retriever.embed_texts", mock_embed):
        chunks = retrieve_chunks("Where does Manikandan work?", mock_vs, mock_cache)

    assert any(c.doc_name == "resume.pdf" for c in chunks)


def test_neighbor_expansion_includes_adjacent_chunks():
    # Selecting one chunk should widen to its neighbours so split info is reassembled.
    mock_vs = MagicMock()
    mock_vs.count.return_value = 3
    mock_vs.search.return_value = _make_chroma_response(
        scores=[0.5, 0.1, 0.6],  # sims 0.5, 0.9, 0.4 -> idx1 is the top primary
        texts=["intro", "the key answer", "trailing detail"],
        metadatas=[
            {"source_file": "doc.pdf", "page_number": 1, "chunk_index": 0},
            {"source_file": "doc.pdf", "page_number": 1, "chunk_index": 1},
            {"source_file": "doc.pdf", "page_number": 1, "chunk_index": 2},
        ],
    )
    mock_cache = MagicMock()
    mock_cache.get_embedding.return_value = None
    mock_embed = MagicMock(return_value=[[0.1] * 384])

    with patch("core.retriever.embed_texts", mock_embed):
        chunks = retrieve_chunks("q", mock_vs, mock_cache, top_k_rerank=1)

    indices = {c.chunk_index for c in chunks}
    assert indices == {0, 1, 2}  # primary idx1 pulled in neighbours idx0 and idx2
