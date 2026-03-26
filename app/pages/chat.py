"""
Chat page: full RAG loop with complexity routing and fallback chain.
Sprint 5 adds multi-turn persistence.
"""
from __future__ import annotations

import time
import uuid
from typing import Optional

import streamlit as st

from config.settings import get_settings
from core.cache.cache_manager import get_cache_manager
from core.complexity_classifier import Tier, classify
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


def _render_message(role: str, content: str, meta: Optional[dict] = None) -> None:
    with st.chat_message(role):
        st.markdown(content)
        if meta and role == "assistant":
            cols = st.columns(4)
            cols[0].markdown(f"**Cache:** {meta.get('cache', 'Fresh')}")
            cols[1].markdown(f"**Tier:** `{meta.get('tier', '-')}`")
            cols[2].markdown(f"**Model:** `{meta.get('model_short', '-')}`")
            cols[3].markdown(f"**Confidence:** {meta.get('confidence', '-')}")
            if meta.get("fallback"):
                st.caption(f"Fallback used: {meta['fallback']}")
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
        turn_count = len(st.session_state["messages"]) // 2
        tier, _ = classify(prompt, turn_count=turn_count)
        st.session_state["messages"].append({"role": "user", "content": prompt, "tier": tier.value})
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
                    model_id = "-"
                    model_short = "-"
                    tokens_in = tokens_out = 0
                    cost = 0.0
                    fallback_tier = None
                else:
                    messages = build_messages(prompt, chunks, history=[])

                    FALLBACK_CHAIN = [
                        (Tier.SIMPLE, s.tier_1_model),
                        (Tier.MODERATE, s.tier_2_model),
                        (Tier.COMPLEX, s.tier_3_model),
                    ]
                    start_idx = next(i for i, (t, _) in enumerate(FALLBACK_CHAIN) if t == tier)

                    answer = None
                    tokens_in = tokens_out = 0
                    cost = 0.0
                    fallback_tier = None
                    model_id = "-"

                    for fb_tier, fb_model in FALLBACK_CHAIN[start_idx:]:
                        try:
                            answer, tokens_in, tokens_out, cost = call_llm(messages, fb_model)
                            model_id = fb_model
                            if fb_tier != tier:
                                fallback_tier = fb_tier.value
                            break
                        except LLMUnavailableError:
                            continue

                    if answer is None:
                        raise LLMUnavailableError("All tiers exhausted")

                    confidence = score_confidence(chunks)
                    model_short = model_id.split("/")[-1]
                    sources_meta = [
                        {"doc_name": c.doc_name, "page": c.page_number, "text": c.text, "score": c.score}
                        for c in chunks
                    ]

                latency_ms = int((time.time() - t0) * 1000)
                meta = {
                    "cache": "Fresh",
                    "tier": tier.value,
                    "model_short": model_short,
                    "fallback": fallback_tier,
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
