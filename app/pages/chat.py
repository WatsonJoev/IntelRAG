"""
Chat page: full RAG loop with LLM, streaming, badges.
Sprint 3 adds complexity routing. Sprint 5 adds multi-turn persistence.
"""
from __future__ import annotations

import time
import uuid

import streamlit as st

from config.settings import get_settings
from core.cache.cache_manager import get_cache_manager
from core.confidence import score_confidence
from core.llm_service import LLMUnavailableError, call_llm
from core.prompt_builder import build_messages
from core.retriever import retrieve_chunks
from core.storage.vector_store import VectorStore


def _init_session() -> None:
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())
    if "messages" not in st.session_state:
        st.session_state["messages"] = []


def _render_message(role: str, content: str, meta: dict = None) -> None:
    with st.chat_message(role):
        st.markdown(content)
        if meta and role == "assistant":
            cols = st.columns(3)
            cols[0].markdown(f"**Cache:** {meta.get('cache', 'Fresh')}")
            cols[1].markdown(f"**Model:** `{meta.get('model_short', '-')}`")
            cols[2].markdown(f"**Confidence:** {meta.get('confidence', '-')}")
            if meta.get("sources"):
                with st.expander("Sources", expanded=False):
                    for i, src in enumerate(meta["sources"], 1):
                        pg = f", page {src['page']}" if src.get("page") else ""
                        st.markdown(f"**[Source {i}]** `{src['doc_name']}`{pg} (score: {src['score']:.2f})")
                        st.caption(src["text"][:300] + ("..." if len(src["text"]) > 300 else ""))


def main() -> None:
    _init_session()
    s = get_settings()
    st.title("IntelRAG Chat")

    with st.sidebar:
        st.header("Session")
        if st.button("New Conversation"):
            st.session_state["messages"] = []
            st.session_state["session_id"] = str(uuid.uuid4())
            st.rerun()
        st.caption(f"Session: `{st.session_state['session_id'][:8]}...`")

    for msg in st.session_state["messages"]:
        _render_message(msg["role"], msg["content"], msg.get("meta"))

    if prompt := st.chat_input("Ask a question about your documents..."):
        st.session_state["messages"].append({"role": "user", "content": prompt})
        _render_message("user", prompt)

        with st.spinner("Thinking..."):
            try:
                t0 = time.time()
                cache_mgr = get_cache_manager()
                vs = VectorStore()

                chunks = retrieve_chunks(prompt, vs, cache_mgr)
                if not chunks:
                    answer = "I don't have enough information in the indexed documents to answer this."
                    sources_meta = []
                    confidence = "LOW"
                    model_used = "-"
                    model_short = "-"
                    tokens_in = tokens_out = 0
                    cost = 0.0
                else:
                    messages = build_messages(prompt, chunks, history=[])
                    model_id = s.tier_1_model

                    answer, tokens_in, tokens_out, cost = call_llm(messages, model_id)
                    confidence = score_confidence(chunks)
                    model_short = model_id.split("/")[-1]
                    sources_meta = [
                        {"doc_name": c.doc_name, "page": c.page_number, "text": c.text, "score": c.score}
                        for c in chunks
                    ]

                latency_ms = int((time.time() - t0) * 1000)
                meta = {
                    "cache": "Fresh",
                    "model_short": model_short,
                    "confidence": f"{'GREEN' if confidence == 'HIGH' else 'YELLOW' if confidence == 'MEDIUM' else 'RED'} {confidence}",
                    "sources": sources_meta,
                }
                st.session_state["messages"].append(
                    {"role": "assistant", "content": answer, "meta": meta}
                )
                _render_message("assistant", answer, meta)

            except LLMUnavailableError as e:
                err = f"LLM unavailable: {e}"
                st.error(err)
                st.session_state["messages"].append({"role": "assistant", "content": err})
            except Exception as e:
                err = f"Unexpected error: {e}"
                st.error(err)


main()
