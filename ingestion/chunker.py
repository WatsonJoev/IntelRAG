"""
Chunking module with configurable strategy.
Default: recursive character splitting (1000 chars, 200 overlap).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from config.settings import get_settings

# Sentence boundary: end punctuation + whitespace, followed by a likely sentence
# start (capital, digit, or opening quote/paren). Decimals like "3.14" are safe
# (no whitespace after the dot); abbreviations are re-joined in split_sentences.
_SENTENCE_RE = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"\'(\[])')
_PARAGRAPH_RE = re.compile(r"\n\s*\n")
# Common abbreviations that shouldn't end a sentence.
_ABBREVIATIONS = {
    "dr", "mr", "mrs", "ms", "prof", "sr", "jr", "st", "vs", "etc", "inc",
    "ltd", "co", "corp", "e.g", "i.e", "fig", "no", "vol", "pp", "al", "approx",
}


@dataclass
class Chunk:
    text: str
    index: int
    char_offset: int
    page_number: int | None = None
    metadata: dict | None = None

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}


def recursive_split(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    separators: list[str] | None = None,
) -> list[str]:
    """
    Split text by separators (paragraph, newline, space) without breaking mid-sentence when possible.
    """
    if separators is None:
        separators = ["\n\n", "\n", ". ", " "]
    if not text.strip():
        return []
    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= chunk_size:
            chunks.append(remaining.strip())
            break
        chunk = remaining[: chunk_size + 1]
        best_sep = -1
        for sep in separators:
            pos = chunk.rfind(sep)
            if pos > best_sep:
                best_sep = pos
        if best_sep <= 0:
            best_sep = chunk_size
        else:
            best_sep += 1 if chunk[best_sep : best_sep + 1] in " \n" else 0
        part = remaining[:best_sep].strip()
        if part:
            chunks.append(part)
        # Advance the window. Never overlap back further than what we just
        # consumed, so the start always moves forward by at least one char.
        # (When a separator lands within the overlap window, honoring the full
        # overlap would leave `remaining` unchanged and loop forever.)
        overlap = min(chunk_overlap, best_sep - 1)
        overlap_start = max(1, best_sep - overlap)
        prev_len = len(remaining)
        remaining = remaining[overlap_start:].strip()
        if len(remaining) >= prev_len:  # safety net: no forward progress
            break
    return chunks


def split_sentences(text: str) -> list[str]:
    """Split text into sentences, respecting paragraph breaks and abbreviations."""
    text = text.strip()
    if not text:
        return []
    sentences: list[str] = []
    for para in _PARAGRAPH_RE.split(text):
        para = para.strip()
        if not para:
            continue
        merged: list[str] = []
        for candidate in _SENTENCE_RE.split(para):
            # Re-join a split that actually followed an abbreviation ("Dr. Smith").
            if merged:
                prev_words = merged[-1].rsplit(None, 1)
                last_word = prev_words[-1].rstrip(".").lower() if prev_words else ""
                if last_word in _ABBREVIATIONS:
                    merged[-1] = f"{merged[-1]} {candidate}"
                    continue
            merged.append(candidate)
        sentences.extend(m.strip() for m in merged if m.strip())
    return sentences


def sentence_aware_split(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[str]:
    """
    Pack whole sentences greedily up to ``chunk_size`` so chunks never cut
    mid-sentence. Overlap is applied by re-including trailing sentences of the
    previous chunk (up to ``chunk_overlap`` chars), keeping overlaps coherent.
    A single sentence longer than ``chunk_size`` falls back to character
    splitting so it can't be dropped.
    """
    sentences = split_sentences(text)
    if not sentences:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    def flush() -> list[str]:
        chunks.append(" ".join(current))
        # Carry trailing sentences (newest first) up to the overlap budget.
        carried: list[str] = []
        carried_len = 0
        for sent in reversed(current):
            if carried_len + len(sent) > chunk_overlap:
                break
            carried.insert(0, sent)
            carried_len += len(sent) + 1
        return carried

    for sent in sentences:
        if len(sent) > chunk_size:
            if current:
                flush()
                current, current_len = [], 0
            chunks.extend(recursive_split(sent, chunk_size, chunk_overlap))
            continue
        if current and current_len + len(sent) + 1 > chunk_size:
            current = flush()
            current_len = sum(len(s) + 1 for s in current)
        current.append(sent)
        current_len += len(sent) + 1

    if current:
        chunks.append(" ".join(current))
    return chunks


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    max_chunks: int | None = None,
    page_number: int | None = None,
) -> list[Chunk]:
    """
    Chunk text into coherent, sentence-aware pieces. Returns list of Chunk with
    index and offset.
    """
    s = get_settings()
    chunk_size = chunk_size or s.chunk_size
    chunk_overlap = chunk_overlap or s.chunk_overlap
    max_chunks = max_chunks or s.max_chunks_per_doc
    parts = sentence_aware_split(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if len(parts) > max_chunks:
        parts = parts[:max_chunks]
    chunks: list[Chunk] = []
    offset = 0
    for i, p in enumerate(parts):
        chunks.append(
            Chunk(
                text=p,
                index=i,
                char_offset=offset,
                page_number=page_number,
                metadata={},
            )
        )
        offset += len(p) + 2
    return chunks


def chunk_parsed_document(
    full_text: str,
    page_count: int = 1,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    max_chunks_per_doc: int | None = None,
) -> list[Chunk]:
    """
    Chunk a parsed document (single text). If page boundaries are known, pass page_count;
    otherwise treated as single page.
    """
    return chunk_text(
        full_text,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        max_chunks=max_chunks_per_doc,
        page_number=1 if page_count <= 1 else None,
    )
