"""
Admin dashboard: KPIs, cost breakdown, cache metrics, query audit log, health status.
Design: Dark mode enterprise SaaS — blue accent, amber highlights, bento-grid layout.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from datetime import date, datetime, timedelta
from typing import Optional

import streamlit as st

# Dark mode CSS
DARK_CSS = """
<style>
/* Dark enterprise theme */
.stApp {
    background-color: #0a0a0f;
    color: #e2e8f0;
}
[data-testid="stSidebar"] {
    background-color: #0f0f1a;
    border-right: 1px solid #1e293b;
}
/* KPI cards */
.kpi-card {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    border: 1px solid #2d3748;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
    margin-bottom: 8px;
}
.kpi-value {
    font-size: 2.2rem;
    font-weight: 700;
    color: #3b82f6;
    font-family: 'Fira Code', monospace;
    margin: 4px 0;
}
.kpi-label {
    font-size: 0.8rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-weight: 500;
}
.kpi-delta {
    font-size: 0.75rem;
    color: #10b981;
    margin-top: 4px;
}
/* Section headers */
.section-header {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #64748b;
    font-weight: 600;
    margin-bottom: 12px;
    padding-bottom: 6px;
    border-bottom: 1px solid #1e293b;
}
/* Health dots */
.health-dot {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-right: 6px;
}
.dot-green { background-color: #10b981; box-shadow: 0 0 6px #10b981; }
.dot-red { background-color: #ef4444; box-shadow: 0 0 6px #ef4444; }
.dot-yellow { background-color: #f59e0b; box-shadow: 0 0 6px #f59e0b; }
.health-row {
    display: flex;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid #1e293b;
    font-size: 0.875rem;
}
.health-label { color: #94a3b8; flex: 1; }
.health-status { color: #e2e8f0; font-size: 0.8rem; }
/* Metric row */
.metric-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid #1e293b;
    font-size: 0.875rem;
}
.metric-name { color: #94a3b8; }
.metric-value { color: #e2e8f0; font-family: monospace; font-weight: 600; }
.metric-cost { color: #f97316; font-family: monospace; }
</style>
"""


def _get_today_stats():
    """Fetch today's query stats from DB."""
    try:
        from models.db import QueryLog, TokenUsage, Document
        from models.session import get_db
        today = date.today()
        with get_db() as db:
            total_queries = db.query(QueryLog).filter(
                QueryLog.timestamp >= datetime.combine(today, datetime.min.time())
            ).count()
            cache_hits = db.query(QueryLog).filter(
                QueryLog.timestamp >= datetime.combine(today, datetime.min.time()),
                QueryLog.cache_tier_hit.isnot(None)
            ).count()
            docs_total = db.query(Document).filter(Document.status == "indexed").count()
            token_row = db.query(TokenUsage).filter(TokenUsage.date == today).first()
            total_cost = token_row.total_cost if token_row else 0.0
            # Estimate cost saved from cache hits
            cost_saved = cache_hits * 0.002  # ~$0.002 avg per query
        cache_rate = (cache_hits / total_queries * 100) if total_queries > 0 else 0.0
        return {
            "total_queries": total_queries,
            "cache_hits": cache_hits,
            "cache_rate": cache_rate,
            "cost_saved": cost_saved,
            "docs_total": docs_total,
            "total_cost": total_cost,
        }
    except Exception:
        return {"total_queries": 0, "cache_hits": 0, "cache_rate": 0.0, "cost_saved": 0.0, "docs_total": 0, "total_cost": 0.0}


def _get_cost_breakdown():
    """Get cost breakdown by tier for today."""
    try:
        from models.db import TokenUsage
        from models.session import get_db
        today = date.today()
        with get_db() as db:
            row = db.query(TokenUsage).filter(TokenUsage.date == today).first()
        if not row:
            return {"tier1": (0, 0.0), "tier2": (0, 0.0), "tier3": (0, 0.0), "total": 0.0}
        return {
            "tier1": (row.tier_1_tokens, row.tier_1_cost),
            "tier2": (row.tier_2_tokens, row.tier_2_cost),
            "tier3": (row.tier_3_tokens, row.tier_3_cost),
            "total": row.total_cost,
        }
    except Exception:
        return {"tier1": (0, 0.0), "tier2": (0, 0.0), "tier3": (0, 0.0), "total": 0.0}


def _get_cache_stats():
    """Get cache performance stats."""
    try:
        from core.cache.cache_manager import get_cache_manager
        return get_cache_manager().get_stats()
    except Exception:
        return {"tier1_hits": 0, "tier2_hits": 0, "tier3_hits": 0, "misses": 0}


def _get_recent_queries(limit: int = 100, search: str = ""):
    """Get recent queries from QueryLog."""
    try:
        from models.db import QueryLog
        from models.session import get_db
        with get_db() as db:
            q = db.query(QueryLog).order_by(QueryLog.timestamp.desc())
            rows = q.limit(limit * 3).all()  # fetch extra to allow search filtering
        data = []
        for row in rows:
            text = row.query_text or ""
            if search and search.lower() not in text.lower():
                continue
            data.append({
                "Timestamp": row.timestamp.strftime("%Y-%m-%d %H:%M:%S") if row.timestamp else "",
                "Query": text[:80] + ("..." if len(text) > 80 else ""),
                "Model": row.model_used.split("/")[-1] if row.model_used else "",
                "Tier": row.model_tier or "",
                "Tokens": row.tokens_in + row.tokens_out,
                "Cost": f"${row.cost_usd:.4f}",
                "Cache": row.cache_tier_hit or "FRESH",
                "Confidence": row.confidence or "",
                "Latency (ms)": row.latency_ms or 0,
            })
            if len(data) >= limit:
                break
        return data
    except Exception:
        return []


def _get_health():
    """Run health checks."""
    try:
        from core.health import check_all
        return check_all()
    except Exception:
        return {"vector_store": False, "metadata_db": False, "cache": False, "openrouter": False}


def render() -> None:
    st.markdown(DARK_CSS, unsafe_allow_html=True)
    st.markdown("## IntelRAG Admin")
    st.markdown('<p style="color:#64748b;font-size:0.85rem;margin-top:-12px;">System metrics · Cost tracking · Audit log · Health</p>', unsafe_allow_html=True)

    # Auto-refresh toggle
    col_refresh, col_spacer = st.columns([1, 5])
    with col_refresh:
        auto_refresh = st.checkbox("Auto-refresh", value=False, help="Refresh every 30s")

    # Load data
    stats = _get_today_stats()
    cost = _get_cost_breakdown()
    cache_stats = _get_cache_stats()
    health = _get_health()

    st.markdown("---")

    # --- Row 1: KPI Cards ---
    st.markdown('<div class="section-header">Today\'s Overview</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Queries Today</div>
            <div class="kpi-value">{stats['total_queries']}</div>
            <div class="kpi-delta">{stats['cache_hits']} cache hits</div>
        </div>""", unsafe_allow_html=True)

    with c2:
        rate_color = "#10b981" if stats['cache_rate'] > 50 else "#f59e0b" if stats['cache_rate'] > 20 else "#ef4444"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Cache Hit Rate</div>
            <div class="kpi-value" style="color:{rate_color}">{stats['cache_rate']:.1f}%</div>
            <div class="kpi-delta">T1: {cache_stats['tier1_hits']} · T2: {cache_stats['tier2_hits']}</div>
        </div>""", unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Est. Cost Saved</div>
            <div class="kpi-value" style="color:#10b981">${stats['cost_saved']:.4f}</div>
            <div class="kpi-delta">via cache hits</div>
        </div>""", unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Docs Indexed</div>
            <div class="kpi-value">{stats['docs_total']}</div>
            <div class="kpi-delta">Total cost: ${stats['total_cost']:.4f}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Row 2: Cost Breakdown + Cache Performance ---
    left_col, right_col = st.columns(2)

    with left_col:
        st.markdown('<div class="section-header">Cost Breakdown by Tier</div>', unsafe_allow_html=True)
        tiers = [
            ("Tier 1 — Llama Free", cost["tier1"][0], cost["tier1"][1], "#3b82f6"),
            ("Tier 2 — Gemini Flash", cost["tier2"][0], cost["tier2"][1], "#8b5cf6"),
            ("Tier 3 — GPT-4o-mini", cost["tier3"][0], cost["tier3"][1], "#f97316"),
        ]
        for name, tokens, usd, color in tiers:
            st.markdown(f"""
            <div class="metric-row">
                <span class="metric-name">{name}</span>
                <span style="font-family:monospace;font-size:0.8rem;color:{color}">{tokens:,} tok</span>
                <span class="metric-cost">${usd:.5f}</span>
            </div>""", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="metric-row" style="border-top:2px solid #2d3748;margin-top:8px;padding-top:12px;">
            <span style="color:#e2e8f0;font-weight:600">Total</span>
            <span></span>
            <span class="metric-cost" style="font-size:1rem;font-weight:700">${cost['total']:.5f}</span>
        </div>""", unsafe_allow_html=True)

    with right_col:
        st.markdown('<div class="section-header">Cache Performance</div>', unsafe_allow_html=True)
        total_lookups = cache_stats["tier1_hits"] + cache_stats["tier2_hits"] + cache_stats["misses"]
        hit_rate = ((cache_stats["tier1_hits"] + cache_stats["tier2_hits"]) / total_lookups * 100) if total_lookups > 0 else 0

        if total_lookups > 0:
            st.progress(min(hit_rate / 100, 1.0), text=f"Overall hit rate: {hit_rate:.1f}%")

        cache_rows = [
            ("Tier 1 Exact Hits", cache_stats["tier1_hits"], "#3b82f6"),
            ("Tier 2 Semantic Hits", cache_stats["tier2_hits"], "#8b5cf6"),
            ("Tier 3 Embedding Cache", cache_stats.get("tier3_hits", 0), "#10b981"),
            ("Cache Misses", cache_stats["misses"], "#64748b"),
        ]
        for label, count, color in cache_rows:
            st.markdown(f"""
            <div class="metric-row">
                <span class="metric-name">{label}</span>
                <span style="color:{color};font-family:monospace;font-weight:600">{count}</span>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Row 3: Query Audit Log ---
    st.markdown('<div class="section-header">Query Audit Log</div>', unsafe_allow_html=True)
    search = st.text_input("Search queries", placeholder="Filter by query text...", label_visibility="collapsed")
    queries = _get_recent_queries(limit=50, search=search)

    if queries:
        import pandas as pd
        df = pd.DataFrame(queries)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Timestamp": st.column_config.TextColumn("Timestamp", width="medium"),
                "Query": st.column_config.TextColumn("Query", width="large"),
                "Model": st.column_config.TextColumn("Model", width="small"),
                "Tier": st.column_config.TextColumn("Tier", width="small"),
                "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
                "Cost": st.column_config.TextColumn("Cost", width="small"),
                "Cache": st.column_config.TextColumn("Cache", width="small"),
                "Confidence": st.column_config.TextColumn("Conf.", width="small"),
                "Latency (ms)": st.column_config.NumberColumn("Latency (ms)", format="%d ms"),
            },
        )
        st.caption(f"Showing {len(queries)} queries")
    else:
        st.markdown("""
        <div style="text-align:center;padding:40px;color:#475569;border:1px dashed #2d3748;border-radius:8px;margin:16px 0;">
            <div style="font-size:2rem;margin-bottom:8px;">&#128202;</div>
            <div>No queries yet. Ask questions in the Chat page to see logs here.</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Row 4: Health Status ---
    st.markdown('<div class="section-header">System Health</div>', unsafe_allow_html=True)
    health_items = [
        ("Vector Store (ChromaDB)", health.get("vector_store", False)),
        ("Metadata DB (SQLite)", health.get("metadata_db", False)),
        ("Cache (Redis/fakeredis)", health.get("cache", False)),
        ("OpenRouter API", health.get("openrouter", False)),
    ]

    h_cols = st.columns(4)
    for i, (name, ok) in enumerate(health_items):
        with h_cols[i]:
            status_text = "Healthy" if ok else "Unavailable"
            status_color = "#10b981" if ok else "#ef4444"
            indicator = "&#128994;" if ok else "&#128308;"
            st.markdown(f"""
            <div style="background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:16px;text-align:center;">
                <div style="margin-bottom:8px;font-size:0.75rem;color:#64748b;text-transform:uppercase;letter-spacing:0.05em">{name}</div>
                <div style="font-size:1.5rem;">{indicator}</div>
                <div style="color:{status_color};font-size:0.8rem;font-weight:600;margin-top:4px">{status_text}</div>
            </div>""", unsafe_allow_html=True)

    if auto_refresh:
        import time
        time.sleep(30)
        st.rerun()
