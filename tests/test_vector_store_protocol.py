# tests/test_vector_store_protocol.py
from core.storage.vector_store import VectorStore, VectorStoreProtocol


def test_vector_store_implements_protocol():
    assert issubclass(VectorStore, VectorStoreProtocol)
