"""
IntelRAG Streamlit UI — DISABLED.

The Streamlit interface has been superseded by the FastAPI v2 UI which includes
full security controls (auth, CSRF, rate limiting, security headers, etc.).

Run the v2 UI instead:
    uvicorn web.server:app --reload --port 8600
    Open http://localhost:8600

This file is retained for reference; it is not the active application entry point.
"""
import sys

import streamlit as st

st.set_page_config(page_title="IntelRAG — Moved", page_icon="⚠️")
st.error("The Streamlit UI is disabled. Please use the FastAPI v2 interface.")
st.info("Run: `uvicorn web.server:app --reload --port 8600`  →  http://localhost:8600")
sys.exit(0)
