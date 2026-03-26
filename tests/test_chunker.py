"""Tests for ingestion.chunker."""
from __future__ import annotations

import pytest
from ingestion.chunker import chunk_text, recursive_split


def test_recursive_split_small() -> None:
    out = recursive_split("hello world", chunk_size=100, chunk_overlap=10)
    assert out == ["hello world"]


def test_recursive_split_large() -> None:
    text = "a " * 500
    out = recursive_split(text, chunk_size=100, chunk_overlap=20)
    assert len(out) >= 2
    assert "".join(out).replace(" ", "") == text.replace(" ", "")


def test_chunk_text() -> None:
    chunks = chunk_text("First. Second. Third.", chunk_size=20, chunk_overlap=5)
    assert len(chunks) >= 1
    assert chunks[0].index == 0
    assert chunks[0].char_offset == 0
