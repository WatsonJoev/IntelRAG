"""Document Manager page: upload files, list, delete."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from config.settings import get_settings
from core.cache.cache_manager import get_cache_manager
from ingestion.pipeline import ingest_document
from models import get_db
from models.db import Document

from core.storage.file_store import FileStore


def render() -> None:
    st.header("Document Manager")
    settings = get_settings()
    max_mb = settings.max_file_size_mb
    max_bytes = max_mb * 1024 * 1024

    uploaded = st.file_uploader(
        "Upload documents",
        type=["pdf", "docx", "txt", "md", "csv", "xlsx", "xls"],
        accept_multiple_files=True,
        help=f"Max {max_mb} MB per file. Supported: PDF, DOCX, TXT, MD, CSV, XLSX.",
    )

    if uploaded:
        file_store = FileStore(base_path=settings.file_store_path)
        for f in uploaded:
            if f.size > max_bytes:
                st.error(f"File too large: {f.name} ({f.size / 1024 / 1024:.1f} MB). Max {max_mb} MB.")
                continue
            with st.spinner(f"Processing {f.name}..."):
                content = f.read()
                doc_id, status = ingest_document(content, f.name, file_store=file_store)
                if status == "indexed":
                    st.success(f"Indexed: {f.name}")
                elif status == "duplicate":
                    st.info(f"Duplicate skipped: {f.name}")
                else:
                    st.error(f"Failed: {f.name}")

    st.divider()
    st.subheader("Indexed documents")
    with get_db() as db:
        docs = db.query(Document).filter(Document.status == "indexed").order_by(Document.created_at.desc()).all()
    if not docs:
        st.info("No documents yet. Upload files above.")
        return
    for d in docs:
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.text(f"{d.filename} — {d.chunk_count} chunks, {d.page_count} pages")
        with col2:
            st.caption(f"{d.file_size / 1024:.1f} KB")
        with col3:
            if st.button("Delete", key=f"del_{d.id}"):
                with get_db() as db2:
                    doc = db2.get(Document, d.id)
                    if doc:
                        file_store = FileStore(base_path=settings.file_store_path)
                        file_store.delete_document(d.id)
                        # TODO: delete from vector store
                        doc.status = "deleted"
                        db2.commit()
                        get_cache_manager().invalidate_on_doc_change()
                st.rerun()
