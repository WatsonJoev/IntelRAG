"""Document Manager: upload, view, delete indexed documents."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from typing import Optional

import streamlit as st

from config.settings import get_settings
from core.cache.cache_manager import get_cache_manager
from core.storage.file_store import FileStore
from ingestion.pipeline import ingest_document
from models import get_db
from models.db import Document

SUPPORTED_TYPES = ["pdf", "docx", "txt", "md", "csv", "xlsx", "xls", "pptx", "html", "htm", "json", "xml"]

FILE_TYPE_COLORS = {
    ".pdf": "#ef4444",
    ".docx": "#3b82f6",
    ".txt": "#6b7280",
    ".md": "#8b5cf6",
    ".csv": "#10b981",
    ".xlsx": "#10b981",
    ".xls": "#10b981",
    ".pptx": "#f97316",
    ".html": "#f59e0b",
    ".htm": "#f59e0b",
    ".json": "#06b6d4",
    ".xml": "#84cc16",
}

DOC_CSS = """
<style>
.doc-row {
    display: flex;
    align-items: center;
    padding: 12px 16px;
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 8px;
    margin-bottom: 6px;
    gap: 12px;
}
.doc-badge {
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    min-width: 44px;
    text-align: center;
    font-family: monospace;
}
.doc-name {
    flex: 1;
    color: #e2e8f0;
    font-size: 0.875rem;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.doc-meta {
    color: #64748b;
    font-size: 0.75rem;
    white-space: nowrap;
}
.upload-zone {
    border: 2px dashed #2d3748;
    border-radius: 12px;
    padding: 32px;
    text-align: center;
    background: #0a0a0f;
    margin-bottom: 24px;
}
.status-indexed {
    color: #10b981;
    font-size: 0.7rem;
    font-weight: 600;
}
</style>
"""


def _file_badge(ext: str) -> str:
    color = FILE_TYPE_COLORS.get(ext.lower(), "#6b7280")
    label = ext.upper().lstrip(".") or "FILE"
    return f'<span class="doc-badge" style="background:{color}22;color:{color};border:1px solid {color}44">{label}</span>'


def _format_size(bytes_val: int) -> str:
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    else:
        return f"{bytes_val / 1024 / 1024:.1f} MB"


def render() -> None:
    st.markdown(DOC_CSS, unsafe_allow_html=True)
    st.markdown("## Document Manager")
    st.markdown('<p style="color:#64748b;font-size:0.85rem;margin-top:-12px;">Upload · Index · Manage your knowledge base</p>', unsafe_allow_html=True)

    settings = get_settings()
    max_mb = settings.max_file_size_mb
    max_bytes = max_mb * 1024 * 1024

    # Upload section
    st.markdown("---")
    uploaded = st.file_uploader(
        f"Upload documents (max {max_mb} MB each)",
        type=SUPPORTED_TYPES,
        accept_multiple_files=True,
        help=f"Supported: {', '.join(t.upper() for t in SUPPORTED_TYPES[:8])} + more",
    )

    # Track processed files to prevent rerun loop:
    # Streamlit keeps uploaded files in widget state after rerun, so without
    # this guard the upload block fires on every rerun causing an infinite loop.
    if "processed_upload_keys" not in st.session_state:
        st.session_state["processed_upload_keys"] = set()

    if uploaded:
        # Fingerprint each file by name+size to detect already-processed files
        pending = [f for f in uploaded
                   if f"{f.name}:{f.size}" not in st.session_state["processed_upload_keys"]]

        if pending:
            file_store = FileStore(base_path=settings.file_store_path)
            progress_bar = st.progress(0)
            newly_indexed = False
            for idx, f in enumerate(pending):
                progress_bar.progress((idx + 1) / len(pending), text=f"Processing {f.name}...")
                st.session_state["processed_upload_keys"].add(f"{f.name}:{f.size}")
                if f.size > max_bytes:
                    st.error(f"**{f.name}** exceeds {max_mb} MB limit ({_format_size(f.size)})")
                    continue
                content = f.read()
                doc_id, status = ingest_document(content, f.name, file_store=file_store)
                if status == "indexed":
                    st.success(f"Indexed: **{f.name}**")
                    newly_indexed = True
                elif status == "duplicate":
                    st.info(f"Already exists: **{f.name}** (skipped)")
                else:
                    st.error(f"Failed to process: **{f.name}**")
            progress_bar.empty()
            if newly_indexed:
                st.rerun()  # Refresh document list only when something was actually added

    # Document list
    st.markdown("---")
    with get_db() as db:
        docs = (
            db.query(Document)
            .filter(Document.status == "indexed")
            .order_by(Document.created_at.desc())
            .all()
        )

    if not docs:
        st.markdown("""
        <div style="text-align:center;padding:60px;color:#475569;border:1px dashed #2d3748;border-radius:12px">
            <div style="font-size:3rem;margin-bottom:12px">&#128194;</div>
            <div style="font-size:1.1rem;font-weight:500">No documents indexed yet</div>
            <div style="font-size:0.875rem;margin-top:8px">Upload files above to start building your knowledge base</div>
        </div>""", unsafe_allow_html=True)
        return

    total_chunks = sum(d.chunk_count for d in docs)
    total_size = sum(d.file_size for d in docs)

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Documents", len(docs))
    col_b.metric("Total Chunks", f"{total_chunks:,}")
    col_c.metric("Storage Used", _format_size(total_size))

    st.markdown("<br>", unsafe_allow_html=True)

    # Sort controls
    sort_col, filter_col = st.columns([2, 2])
    with sort_col:
        sort_by = st.selectbox("Sort by", ["Newest first", "Oldest first", "Name A-Z", "Largest first", "Most chunks"], label_visibility="collapsed")
    with filter_col:
        filter_type = st.selectbox("Filter type", ["All types"] + sorted(set(Path(d.filename).suffix.lower() for d in docs if Path(d.filename).suffix)), label_visibility="collapsed")

    # Apply sort
    sorted_docs = list(docs)
    if sort_by == "Oldest first":
        sorted_docs.sort(key=lambda d: d.created_at)
    elif sort_by == "Name A-Z":
        sorted_docs.sort(key=lambda d: d.filename.lower())
    elif sort_by == "Largest first":
        sorted_docs.sort(key=lambda d: d.file_size, reverse=True)
    elif sort_by == "Most chunks":
        sorted_docs.sort(key=lambda d: d.chunk_count, reverse=True)

    # Apply filter
    if filter_type != "All types":
        sorted_docs = [d for d in sorted_docs if Path(d.filename).suffix.lower() == filter_type]

    st.markdown(f'<div style="color:#64748b;font-size:0.8rem;margin-bottom:12px">Showing {len(sorted_docs)} of {len(docs)} documents</div>', unsafe_allow_html=True)

    for d in sorted_docs:
        ext = Path(d.filename).suffix
        col1, col2 = st.columns([10, 1])
        with col1:
            badge = _file_badge(ext)
            created = d.created_at.strftime("%b %d, %Y") if d.created_at else ""
            st.markdown(f"""
            <div class="doc-row">
                {badge}
                <span class="doc-name" title="{d.filename}">{d.filename}</span>
                <span class="doc-meta">{d.chunk_count} chunks · {d.page_count}p · {_format_size(d.file_size)} · {created}</span>
                <span class="status-indexed">INDEXED</span>
            </div>""", unsafe_allow_html=True)
        with col2:
            if st.button("Del", key=f"del_{d.id}", help=f"Delete {d.filename}", type="secondary"):
                with get_db() as db2:
                    doc = db2.get(Document, d.id)
                    if doc:
                        FileStore(base_path=settings.file_store_path).delete_document(d.id)
                        doc.status = "deleted"
                        db2.commit()
                        get_cache_manager().invalidate_on_doc_change()
                st.rerun()
