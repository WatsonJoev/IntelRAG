"""Tests for ingestion.chunker."""
from __future__ import annotations

from ingestion.chunker import (
    chunk_text,
    recursive_split,
    sentence_aware_split,
    split_sentences,
)


def test_recursive_split_small() -> None:
    out = recursive_split("hello world", chunk_size=100, chunk_overlap=10)
    assert out == ["hello world"]


def test_recursive_split_large() -> None:
    text = "a " * 500
    out = recursive_split(text, chunk_size=100, chunk_overlap=20)
    assert len(out) >= 2
    # An overlapping splitter duplicates content across chunk boundaries, so the
    # joined length is >= the original (never less) and content is uncorrupted.
    joined = "".join(out).replace(" ", "")
    original = text.replace(" ", "")
    assert set(joined) == {"a"}  # no corruption
    assert len(joined) >= len(original)  # no data loss


def test_recursive_split_no_infinite_loop() -> None:
    # Separator falls inside the overlap window; must still terminate.
    out = recursive_split("x " + "y" * 200, chunk_size=100, chunk_overlap=30)
    assert len(out) >= 2
    assert "".join(out).count("y") >= 200


def test_chunk_text() -> None:
    chunks = chunk_text("First. Second. Third.", chunk_size=20, chunk_overlap=5)
    assert len(chunks) >= 1
    assert chunks[0].index == 0
    assert chunks[0].char_offset == 0


def test_split_sentences_respects_boundaries() -> None:
    sents = split_sentences("Dr. Smith earned $3.50. Then he left. He came back!")
    # abbreviations / decimals must not over-split
    assert "Dr. Smith earned $3.50." in sents
    assert sents[-1] == "He came back!"


def test_sentence_aware_no_midsentence_cuts() -> None:
    text = (
        "The revenue was ten million dollars. Costs rose by five percent. "
        "The board approved the budget. Marketing spend will increase. "
        "The outlook remains positive."
    )
    out = sentence_aware_split(text, chunk_size=90, chunk_overlap=25)
    assert len(out) >= 2
    # every chunk ends on a sentence terminator -> no mid-sentence cuts
    assert all(c.rstrip()[-1] in ".!?" for c in out)


def test_sentence_aware_long_sentence_fallback() -> None:
    # A single sentence longer than the budget must still be split (no data loss).
    out = sentence_aware_split("word " * 300, chunk_size=100, chunk_overlap=20)
    assert len(out) >= 2
    assert "".join(out).count("word") >= 300


def test_sentence_aware_empty() -> None:
    assert sentence_aware_split("", 100, 20) == []
