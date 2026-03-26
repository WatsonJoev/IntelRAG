"""Tests for core.storage.file_store."""
from __future__ import annotations

import pytest
from core.storage.file_store import FileStore


def test_save_and_read(file_store: FileStore) -> None:
    file_store.save("doc1", "test.txt", b"hello world")
    content = file_store.read("doc1", "test.txt")
    assert content == b"hello world"


def test_exists(file_store: FileStore) -> None:
    assert not file_store.exists("doc1", "missing.txt")
    file_store.save("doc1", "a.txt", b"x")
    assert file_store.exists("doc1", "a.txt")


def test_content_hash() -> None:
    fs = FileStore(base_path="/tmp/ignored")
    h = fs.content_hash(b"same")
    assert len(h) == 64 and h == fs.content_hash(b"same")
    assert h != fs.content_hash(b"other")


def test_delete_document(file_store: FileStore) -> None:
    file_store.save("d1", "f1.txt", b"a")
    file_store.delete_document("d1")
    assert not file_store.exists("d1", "f1.txt")
