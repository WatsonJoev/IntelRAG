"""
Document ingestion pipeline: file store → parser → chunker → embedder → vector store → metadata DB.
"""
from __future__ import annotations

import hashlib
import time
import uuid
from pathlib import Path

from config.logging_config import get_logger
from core.audit import log_ingestion
from config.settings import get_settings
from core.embedding_service import embed_texts
from core.storage.file_store import FileStore
from core.storage.vector_store import VectorStore
from ingestion.chunker import chunk_parsed_document
from ingestion.parsers.factory import get_parser_for_content
from models import get_db, init_db
from models.db import Chunk as ChunkModel
from models.db import Document

logger = get_logger(__name__)


def _normalize_text(text: str) -> str:
    """Basic normalization: collapse whitespace."""
    return " ".join(text.split())


def ingest_document(
    content: bytes,
    filename: str,
    file_store: FileStore | None = None,
    vector_store: VectorStore | None = None,
) -> tuple[str, str]:
    """
    Ingest one document: save file, parse, chunk, embed, store in vector DB and metadata DB.
    Returns (doc_id, status) where status is "indexed" or "failed".
    """
    s = get_settings()
    file_store = file_store or FileStore(base_path=s.file_store_path)
    vector_store = vector_store or VectorStore()
    doc_id = str(uuid.uuid4())[:12]
    t_start = time.time()

    try:
        content_hash = hashlib.sha256(content).hexdigest()
        # Duplicate check
        with get_db() as db:
            existing = db.query(Document).filter(Document.content_hash == content_hash).first()
            if existing:
                logger.info("duplicate_skipped", doc_id=existing.id, filename=filename)
                log_ingestion(existing.id, "duplicate")
                return existing.id, "duplicate"

        sanitized_name = FileStore._sanitize_filename(Path(filename).name)
        file_store.save(doc_id, filename, content)
        file_store_path = f"{doc_id}/{sanitized_name}"

        parser = get_parser_for_content(content, filename)
        if not parser:
            raise ValueError(f"No parser for file: {filename}")

        parsed = parser.parse(content, filename)
        text = _normalize_text(parsed.text)
        if not text.strip():
            raise ValueError("Empty text after parse")

        chunks = chunk_parsed_document(
            text,
            page_count=parsed.page_count,
            chunk_size=s.chunk_size,
            chunk_overlap=s.chunk_overlap,
            max_chunks_per_doc=s.max_chunks_per_doc,
        )
        if not chunks:
            raise ValueError("No chunks produced")

        texts = [c.text for c in chunks]
        embeddings = embed_texts(texts, batch_size=s.embedding_batch_size)

        ids = [f"{doc_id}_{c.index}" for c in chunks]
        metadatas = [
            {
                "doc_id": doc_id,
                "chunk_index": c.index,
                "page_number": c.page_number or 0,
                "source_file": filename,
                "char_offset": c.char_offset,
            }
            for c in chunks
        ]
        vector_store.add_with_embeddings(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=texts,
        )

        with get_db() as db:
            doc = Document(
                id=doc_id,
                filename=filename,
                file_type=Path(filename).suffix.lower(),
                file_size=len(content),
                content_hash=content_hash,
                file_store_path=file_store_path,
                status="indexed",
                chunk_count=len(chunks),
                page_count=parsed.page_count,
                metadata_json=parsed.metadata,
            )
            db.add(doc)
            for c in chunks:
                ch = ChunkModel(
                    document_id=doc_id,
                    chunk_index=c.index,
                    page_number=c.page_number,
                    char_offset=c.char_offset,
                    vector_store_id=ids[c.index],
                    text_preview=c.text[:500],
                )
                db.add(ch)
            db.commit()

        log_ingestion(doc_id, "success", chunks_created=len(chunks), duration_ms=int((time.time() - t_start) * 1000))
        logger.info(
            "document_indexed",
            doc_id=doc_id,
            filename=filename,
            chunks=len(chunks),
        )
        return doc_id, "indexed"
    except Exception as e:
        logger.exception("ingestion_failed", doc_id=doc_id, filename=filename, error=str(e))
        log_ingestion(doc_id, "failed", error_message=str(e))
        with get_db() as db:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc:
                doc.status = "failed"
                db.commit()
            else:
                doc = Document(
                    id=doc_id,
                    filename=filename,
                    file_type=Path(filename).suffix.lower(),
                    file_size=len(content),
                    content_hash="",
                    file_store_path="",
                    status="failed",
                    chunk_count=0,
                    page_count=0,
                )
                db.add(doc)
                db.commit()
        return doc_id, "failed"
