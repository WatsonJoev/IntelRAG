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

    with patch("core.retriever.embed_texts", mock_embed):
        chunks = retrieve_chunks("test query", mock_vs, mock_cache)

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
