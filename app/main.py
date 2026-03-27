"""
IntelRAG Streamlit app — multi-page entrypoint.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root on path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

# st.set_page_config MUST be the very first Streamlit call
st.set_page_config(
    page_title="IntelRAG",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

from config.logging_config import configure_logging
from config.settings import get_settings
from models.session import ensure_data_dir, init_db

# Module-level flag: Streamlit reruns main.py on every interaction, but
# Python module cache keeps this flag alive so init runs exactly once per process.
_APP_INITIALIZED: list = []  # use a list so it's mutable from module scope

if not _APP_INITIALIZED:
    _settings = get_settings()
    configure_logging(json_logs=_settings.log_json, log_level=_settings.log_level)
    ensure_data_dir()
    init_db()
    _APP_INITIALIZED.append(True)

from app.pages import chat, documents, admin

# Custom CSS for cleaner UI
st.markdown("""
<style>
    .stApp { max-width: 1400px; margin: 0 auto; }
    .uploadedFile { padding: 0.5rem; border-radius: 6px; }
    div[data-testid="stSidebar"] { min-width: 280px; }
</style>
""", unsafe_allow_html=True)

# Sidebar navigation
st.sidebar.title("IntelRAG")
st.sidebar.markdown("Enterprise RAG — upload docs, ask questions.")
page = st.sidebar.radio(
    "Navigate",
    ["Documents", "Chat", "Admin"],
    index=0,
    label_visibility="collapsed",
)

if page == "Documents":
    documents.render()
elif page == "Admin":
    admin.render()
else:
    chat.render()
