"""
Chat page: full RAG loop with complexity routing, fallback, 3-tier cache, multi-turn prep.
Sprint 5 adds full multi-turn persistence.
"""
from __future__ import annotations

import hashlib
import time
import uuid
from typing import Optional

import streamlit as st

from config.settings import get_settings
from core.audit import log_query
from core.cache.cache_manager import get_cache_manager
from core.complexity_classifier import Tier, classify
from core.confidence import score_confidence
from core.llm_service import LLMUnavailableError, call_llm
from core.prompt_builder import build_messages
from core.retriever import retrieve_chunks
from core.schemas import QueryResult
from core.storage.vector_store import VectorStore
from models.db import Conversation, Document
from models.session import get_db


def _compute_doc_set_hash() -> str:
    """SHA-256 fingerprint of all currently indexed documents."""
    with get_db() as db:
        docs = db.query(Document).filter(Document.status == "indexed").all()
        parts = sorted(f"{d.id}:{d.created_at.isoformat()}" for d in docs)
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _load_conversation(session_id: str) -> list:
    """Load messages from SQLite for this session."""
    with get_db() as db:
        conv = db.query(Conversation).filter(
            Conversation.session_id == session_id
        ).order_by(Conversation.updated_at.desc()).first()
    if conv and conv.messages_json:
        return conv.messages_json if isinstance(conv.messages_json, list) else []
    return []


def _save_conversation(session_id: str, messages: list) -> None:
    """Upsert conversation to SQLite."""
    with get_db() as db:
        conv = db.query(Conversation).filter(
            Conversation.session_id == session_id
        ).first()
        if conv:
            conv.messages_json = messages
        else:
            conv = Conversation(
                id=str(uuid.uuid4()),
                user_id="local",
                session_id=session_id,
                messages_json=messages,
            )
            db.add(conv)
        db.commit()


def _init_session() -> None:
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())
    if "messages" not in st.session_state:
        loaded = _load_conversation(st.session_state["session_id"])
        st.session_state["messages"] = loaded


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
            new_sid = str(uuid.uuid4())
            st.session_state["messages"] = []
            st.session_state["session_id"] = new_sid
            _save_conversation(new_sid, [])
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
                doc_set_hash = _compute_doc_set_hash()

                # --- Cache lookup (Tier 1 + Tier 2) ---
                cache_result = cache_mgr.lookup(prompt, doc_set_hash, tier.value)
                if cache_result:
                    badge = "T1 Cache Hit" if cache_result.cache_tier_hit == "TIER_1" else "T2 Semantic Hit"
                    meta = {
                        "cache": badge,
                        "tier": cache_result.model_tier,
                        "model_short": cache_result.model_used.split("/")[-1],
                        "confidence": cache_result.confidence,
                        "sources": [
                            {"doc_name": src.doc_name, "page": src.page_number,
                             "text": src.text, "score": src.score}
                            for src in cache_result.sources
                        ],
                    }
                    st.session_state["messages"].append(
                        {"role": "assistant", "content": cache_result.answer, "meta": meta}
                    )
                    _render_message("assistant", cache_result.answer, meta)
                    log_query(
                        session_id=st.session_state["session_id"],
                        query_text=prompt,
                        model_used=cache_result.model_used,
                        model_tier=cache_result.model_tier,
                        tokens_in=0,
                        tokens_out=0,
                        cost_usd=0.0,
                        latency_ms=int((time.time() - t0) * 1000),
                        cache_tier_hit=cache_result.cache_tier_hit,
                        confidence=cache_result.confidence,
                        chunks_retrieved=cache_result.chunks_retrieved,
                    )
                    _save_conversation(st.session_state["session_id"], st.session_state["messages"])
                    st.stop()

                # --- Retrieval ---
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
                    # Multi-turn history
                    max_turns = s.conversation_history_turns
                    history_msgs = st.session_state["messages"][-(max_turns * 2):-1]
                    history = [{"role": m["role"], "content": m["content"]} for m in history_msgs]
                    messages = build_messages(prompt, chunks, history=history)

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

                    # Store to cache
                    result_obj = QueryResult(
                        answer=answer,
                        sources=chunks,
                        model_used=model_id,
                        model_tier=tier.value,
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                        cost_usd=cost,
                        latency_ms=int((time.time() - t0) * 1000),
                        cache_tier_hit=None,
                        confidence=confidence,
                        fallback_tier=fallback_tier,
                    )
                    cache_mgr.store(prompt, doc_set_hash, tier.value, result_obj)

                latency_ms = int((time.time() - t0) * 1000)

                # Audit log
                log_query(
                    session_id=st.session_state["session_id"],
                    query_text=prompt,
                    model_used=model_id,
                    model_tier=tier.value,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost_usd=cost,
                    latency_ms=latency_ms,
                    cache_tier_hit=None,
                    confidence=confidence,
                    chunks_retrieved=len(chunks),
                    fallback_tier=fallback_tier,
                )

                meta = {
                    "cache": "Fresh",
                    "tier": tier.value,
                    "model_short": model_short,
                    "fallback": fallback_tier,
                    "confidence": confidence,
                    "sources": sources_meta,
                }
                st.session_state["messages"].append(
                    {"role": "assistant", "content": answer, "meta": meta}
                )
                _render_message("assistant", answer, meta)
                _save_conversation(st.session_state["session_id"], st.session_state["messages"])

            except LLMUnavailableError as e:
                err = f"LLM unavailable: {e}"
                st.error(err)
                st.session_state["messages"].append({"role": "assistant", "content": err})
            except Exception as e:
                err = f"Unexpected error: {e}"
                st.error(err)


main()
