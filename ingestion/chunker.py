"""
Chunking module with configurable strategy.
Default: recursive character splitting (1000 chars, 200 overlap).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from config.settings import get_settings


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
        overlap_start = max(0, best_sep - chunk_overlap)
        remaining = remaining[overlap_start:].strip()
        if remaining and len(remaining) == len(chunk) - overlap_start:
            break
    return chunks


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    max_chunks: int | None = None,
    page_number: int | None = None,
) -> list[Chunk]:
    """
    Chunk text using recursive splitting. Returns list of Chunk with index and offset.
    """
    s = get_settings()
    chunk_size = chunk_size or s.chunk_size
    chunk_overlap = chunk_overlap or s.chunk_overlap
    max_chunks = max_chunks or s.max_chunks_per_doc
    parts = recursive_split(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
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
