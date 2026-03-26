"""Chat page: simple Q&A with vector search + placeholder LLM."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from config.settings import get_settings
from core.embedding_service import embed_query
from core.storage.vector_store import VectorStore


def _simple_retrieve(query: str, top_k: int = 5) -> list[dict]:
    """Dense retrieval only (no LLM call). Returns list of {text, metadata}."""
    vs = VectorStore()
    emb = embed_query(query)
    result = vs.search(query_embeddings=[emb], n_results=top_k)
    docs = result.get("documents", [[]])[0] or []
    metadatas = result.get("metadatas", [[]])[0] or []
    return [{"text": t, "metadata": m or {}} for t, m in zip(docs, metadatas)]


def render() -> None:
    st.header("Chat")
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                with st.expander("Sources"):
                    for s in msg["sources"]:
                        st.caption(s.get("text", "")[:200] + "…")

    if prompt := st.chat_input("Ask a question about your documents"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            chunks = _simple_retrieve(prompt, top_k=5)
            if not chunks:
                reply = "No relevant documents found. Upload documents in the Documents page first."
                sources = []
            else:
                # Placeholder: concatenate top chunk texts as "answer" until LLM is wired
                reply = "Based on your documents:\n\n" + "\n\n".join(
                    c["text"][:500] for c in chunks[:3]
                )
                if len(chunks[0]["text"]) > 500:
                    reply += "\n\n..."
                sources = [{"text": c["text"], "metadata": c["metadata"]} for c in chunks]
            st.markdown(reply)
            if sources:
                with st.expander("Sources"):
                    for s in sources:
                        meta = s.get("metadata", {})
                        st.caption(f"Doc: {meta.get('source_file', '?')} — {s['text'][:200]}…")
        st.session_state.messages.append({
            "role": "assistant",
            "content": reply,
            "sources": sources,
        })
