# IntelRAG MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fully demo-able enterprise RAG MVP on top of the existing Phase 1 foundation — adding LLM integration, 3-tier caching, intelligent model routing, and a polished admin UI.

**Architecture:** Vertical slice — each sprint delivers a testable demo checkpoint. Sprint 2 wires a single-model RAG loop end-to-end; S3 adds complexity routing; S4 adds 3-tier fakeredis caching; S5 adds multi-turn memory + confidence; S6 wires audit logging; S7 delivers the polished UI via ui-ux-pro-max.

**Tech Stack:** Python 3.11+, Streamlit, SQLAlchemy + SQLite3, ChromaDB, sentence-transformers, openai SDK (OpenRouter), fakeredis, pytest.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `core/schemas.py` | CREATE | Shared dataclasses: `RetrievedChunk`, `QueryResult`, `CacheEntry` |
| `core/llm_service.py` | CREATE | OpenRouter client, streaming, retry+backoff, fallback chain, `LLMUnavailableError` |
| `core/complexity_classifier.py` | CREATE | Rule-based query → `Tier` enum + model_id |
| `core/retriever.py` | CREATE | Dense vector search, threshold filter, context assembly |
| `core/prompt_builder.py` | CREATE | System prompt, numbered sources, conversation history |
| `core/confidence.py` | CREATE | Similarity scores + chunk count → LOW/MEDIUM/HIGH |
| `core/health.py` | CREATE | `check_all()` pinging ChromaDB/SQLite/cache/OpenRouter |
| `core/audit.py` | CREATE | Audit helpers: `log_query`, `log_ingestion`, `_upsert_token_usage` |
| `core/cache/__init__.py` | CREATE | Package marker |
| `core/cache/redis_client.py` | CREATE | fakeredis wrapper with real-Redis swap interface |
| `core/cache/cache_manager.py` | CREATE | Tier 1 exact + Tier 2 semantic + Tier 3 embedding orchestration |
| `ingestion/parsers/pptx_parser.py` | CREATE | PPTX → text + metadata via python-pptx |
| `ingestion/parsers/html_parser.py` | CREATE | HTML → clean text via BeautifulSoup4 |
| `ingestion/parsers/json_xml_parser.py` | CREATE | JSON/XML → flattened text |
| `ingestion/parsers/factory.py` | MODIFY | Register 3 new parsers |
| `ingestion/pipeline.py` | MODIFY | Add `IngestionLog` writes (stub → real in S6) |
| `core/storage/vector_store.py` | MODIFY | Add `VectorStoreProtocol` ABC for swap-ability |
| `models/db.py` | MODIFY | Add `session_id` to `Conversation`; add `QueryLog`, `TokenUsage`, `IngestionLog` |
| `config/settings.py` | MODIFY | Add `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, `LLM_RETRY_BASE_DELAY`, `CONVERSATION_HISTORY_TURNS` |
| `alembic/versions/002_audit_session.py` | CREATE | Migration: add session_id + 3 audit tables |
| `app/pages/chat.py` | REWRITE | Full RAG chain, streaming, all badges |
| `app/pages/documents.py` | MODIFY | Sortable table, delete cascade, storage indicator |
| `app/pages/admin.py` | CREATE | Admin dashboard (ui-ux-pro-max) |
| `tests/test_schemas.py` | CREATE | Dataclass construction/serialisation |
| `tests/test_complexity_classifier.py` | CREATE | 15+ query samples across all tiers |
| `tests/test_llm_service.py` | CREATE | Mock OpenRouter — streaming, retry, fallback |
| `tests/test_retriever.py` | CREATE | Mock vector store — threshold, dedup, assembly |
| `tests/test_prompt_builder.py` | CREATE | Single-turn and multi-turn prompt structure |
| `tests/test_confidence.py` | CREATE | Score → label boundary tests |
| `tests/test_cache_manager.py` | CREATE | All 3 tiers: hit/miss/invalidation |
| `tests/test_parsers_new.py` | CREATE | PPTX/HTML/JSON/XML parser smoke tests |
| `tests/test_health.py` | CREATE | Health check status dict |

---

## Sprint 1 — Close Phase 1 Gaps

### Task 1.1: Add config keys for LLM + conversation

**Files:**
- Modify: `config/settings.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_settings.py
from config.settings import get_settings

def test_llm_timeout_default():
    get_settings.cache_clear()
    s = get_settings()
    assert s.llm_timeout_seconds == 60
    assert s.llm_max_retries == 3
    assert s.conversation_history_turns == 6
```

- [ ] **Step 2: Run — expect FAIL** (fields don't exist yet)

```bash
pytest tests/test_settings.py -v
```

- [ ] **Step 3: Add 4 new settings fields**

```python
# In class Settings, after `tier_3_model`:

# LLM service
llm_timeout_seconds: int = Field(default=60, alias="LLM_TIMEOUT_SECONDS")
llm_max_retries: int = Field(default=3, alias="LLM_MAX_RETRIES")
llm_retry_base_delay: float = Field(default=1.0, alias="LLM_RETRY_BASE_DELAY")

# Conversation
conversation_history_turns: int = Field(default=6, alias="CONVERSATION_HISTORY_TURNS")
```

- [ ] **Step 4: Verify settings load**

```bash
python -c "from config.settings import get_settings; s = get_settings(); print(s.llm_timeout_seconds, s.conversation_history_turns)"
```
Expected: `60 6`

> **Note:** `get_settings()` uses `@lru_cache`. Any test that patches env vars or needs fresh settings must call `get_settings.cache_clear()` before calling `get_settings()`.

- [ ] **Step 5: Commit**

```bash
git add config/settings.py
git commit -m "feat: add LLM timeout/retry and conversation history settings"
```

---

### Task 1.2: Add VectorStoreProtocol abstraction

**Files:**
- Modify: `core/storage/vector_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vector_store_protocol.py
from core.storage.vector_store import VectorStore, VectorStoreProtocol

def test_vector_store_implements_protocol():
    assert issubclass(VectorStore, VectorStoreProtocol)
```

- [ ] **Step 2: Run it — expect FAIL** (VectorStoreProtocol not defined yet)

```bash
pytest tests/test_vector_store_protocol.py -v
```

- [ ] **Step 3: Add the Protocol to `vector_store.py`** (before the `VectorStore` class)

```python
from typing import Any, Protocol, runtime_checkable

@runtime_checkable
class VectorStoreProtocol(Protocol):
    def add_with_embeddings(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
        documents: list[str] | None = None,
    ) -> None: ...

    def search(
        self,
        query_embeddings: list[list[float]] | None = None,
        query_texts: list[str] | None = None,
        n_results: int = 20,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    def delete(self, ids: list[str] | None = None, where: dict[str, Any] | None = None) -> None: ...

    def count(self) -> int: ...
```

Also update the `VectorStore` class signature:
```python
class VectorStore(VectorStoreProtocol):
```

- [ ] **Step 4: Run test — expect PASS**

```bash
pytest tests/test_vector_store_protocol.py -v
```

- [ ] **Step 5: Commit**

```bash
git add core/storage/vector_store.py tests/test_vector_store_protocol.py
git commit -m "feat: add VectorStoreProtocol abstraction for ChromaDB/Qdrant swap"
```

---

### Task 1.3: PPTX parser

**Files:**
- Create: `ingestion/parsers/pptx_parser.py`
- Create: `tests/test_parsers_new.py` (start it here, extend in 1.4/1.5)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_parsers_new.py
import io
from pptx import Presentation
from pptx.util import Inches
import pytest

def make_pptx_bytes(slide_text: str = "Hello PPTX World") -> bytes:
    prs = Presentation()
    slide_layout = prs.slide_layouts[5]
    slide = prs.slides.add_slide(slide_layout)
    txBox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(2))
    txBox.text_frame.text = slide_text
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()

def test_pptx_parser_extracts_text():
    from ingestion.parsers.pptx_parser import PPTXParser
    parser = PPTXParser()
    result = parser.parse(make_pptx_bytes("Hello PPTX"), "test.pptx")
    assert "Hello PPTX" in result.text
    assert result.page_count >= 1

def test_pptx_parser_supported_extensions():
    from ingestion.parsers.pptx_parser import PPTXParser
    p = PPTXParser()
    assert ".pptx" in p.supported_extensions
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_parsers_new.py::test_pptx_parser_extracts_text -v
```

- [ ] **Step 3: Create `ingestion/parsers/pptx_parser.py`**

```python
"""PPTX parser: extracts text from PowerPoint slides."""
from __future__ import annotations
import io
from pptx import Presentation

from ingestion.parsers.base import BaseParser, ParsedDocument


class PPTXParser(BaseParser):
    supported_extensions = [".pptx"]
    supported_mime_types = [
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    ]

    def parse(self, content: bytes, filename: str) -> ParsedDocument:
        prs = Presentation(io.BytesIO(content))
        texts: list[str] = []
        for slide in prs.slides:
            slide_texts = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        line = " ".join(run.text for run in para.runs).strip()
                        if line:
                            slide_texts.append(line)
            if slide_texts:
                texts.append("\n".join(slide_texts))
        full_text = "\n\n".join(texts)
        metadata = {
            "slide_count": len(prs.slides),
            "filename": filename,
        }
        return ParsedDocument(
            text=full_text,
            page_count=len(prs.slides),
            metadata=metadata,
        )
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/test_parsers_new.py -v
```

- [ ] **Step 5: Register in factory**

In `ingestion/parsers/factory.py`, extend `_get_parsers()`:
```python
from ingestion.parsers.pptx_parser import PPTXParser
# add PPTXParser to the `for cls in (...)` tuple
for cls in (PDFParser, DOCXParser, TXTParser, CSVParser, PPTXParser):
```

- [ ] **Step 6: Commit**

```bash
git add ingestion/parsers/pptx_parser.py ingestion/parsers/factory.py tests/test_parsers_new.py
git commit -m "feat: add PPTX parser with slide text extraction"
```

---

### Task 1.4: HTML parser

**Files:**
- Create: `ingestion/parsers/html_parser.py`
- Modify: `tests/test_parsers_new.py`

- [ ] **Step 1: Add failing tests**

```python
# append to tests/test_parsers_new.py

SAMPLE_HTML = b"""
<html><head><title>Test</title></head>
<body><h1>Hello HTML</h1><p>This is a paragraph.</p></body>
</html>
"""

def test_html_parser_extracts_text():
    from ingestion.parsers.html_parser import HTMLParser
    parser = HTMLParser()
    result = parser.parse(SAMPLE_HTML, "test.html")
    assert "Hello HTML" in result.text
    assert "This is a paragraph" in result.text

def test_html_parser_strips_tags():
    from ingestion.parsers.html_parser import HTMLParser
    parser = HTMLParser()
    result = parser.parse(SAMPLE_HTML, "test.html")
    assert "<h1>" not in result.text
    assert "<p>" not in result.text
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_parsers_new.py::test_html_parser_extracts_text -v
```

- [ ] **Step 3: Create `ingestion/parsers/html_parser.py`**

```python
"""HTML parser: strips tags and extracts clean text via BeautifulSoup4."""
from __future__ import annotations
from bs4 import BeautifulSoup
from ingestion.parsers.base import BaseParser, ParsedDocument


class HTMLParser(BaseParser):
    supported_extensions = [".html", ".htm"]
    supported_mime_types = ["text/html"]

    def parse(self, content: bytes, filename: str) -> ParsedDocument:
        soup = BeautifulSoup(content, "html.parser")
        # Remove script and style elements
        for tag in soup(["script", "style", "head"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        # Collapse multiple blank lines
        lines = [ln for ln in text.splitlines() if ln.strip()]
        full_text = "\n".join(lines)
        title = soup.title.string if soup.title else filename
        return ParsedDocument(
            text=full_text,
            page_count=1,
            metadata={"title": title, "filename": filename},
        )
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/test_parsers_new.py -v
```

- [ ] **Step 5: Register in factory**

```python
from ingestion.parsers.html_parser import HTMLParser
for cls in (PDFParser, DOCXParser, TXTParser, CSVParser, PPTXParser, HTMLParser):
```

- [ ] **Step 6: Commit**

```bash
git add ingestion/parsers/html_parser.py ingestion/parsers/factory.py tests/test_parsers_new.py
git commit -m "feat: add HTML parser with tag stripping via BeautifulSoup4"
```

---

### Task 1.5: JSON + XML parser

**Files:**
- Create: `ingestion/parsers/json_xml_parser.py`
- Modify: `tests/test_parsers_new.py`

- [ ] **Step 1: Add failing tests**

```python
# append to tests/test_parsers_new.py
import json

def test_json_parser_flattens_to_text():
    from ingestion.parsers.json_xml_parser import JSONXMLParser
    data = {"name": "IntelRAG", "version": "1.0", "features": ["rag", "cache"]}
    content = json.dumps(data).encode()
    parser = JSONXMLParser()
    result = parser.parse(content, "config.json")
    assert "IntelRAG" in result.text
    assert "cache" in result.text

def test_xml_parser_extracts_text():
    from ingestion.parsers.json_xml_parser import JSONXMLParser
    xml = b"<root><item>Alpha</item><item>Beta</item></root>"
    parser = JSONXMLParser()
    result = parser.parse(xml, "data.xml")
    assert "Alpha" in result.text
    assert "Beta" in result.text
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_parsers_new.py::test_json_parser_flattens_to_text -v
```

- [ ] **Step 3: Create `ingestion/parsers/json_xml_parser.py`**

```python
"""JSON and XML parser: flattens structured data to readable text."""
from __future__ import annotations
import json
from xml.etree import ElementTree as ET
from ingestion.parsers.base import BaseParser, ParsedDocument


def _flatten_json(obj: object, prefix: str = "") -> list[str]:
    lines: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            lines.extend(_flatten_json(v, f"{prefix}{k}: "))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            lines.extend(_flatten_json(v, f"{prefix}[{i}] "))
    else:
        lines.append(f"{prefix}{obj}")
    return lines


def _extract_xml_text(element: ET.Element) -> list[str]:
    lines: list[str] = []
    if element.text and element.text.strip():
        lines.append(element.text.strip())
    for child in element:
        lines.extend(_extract_xml_text(child))
    if element.tail and element.tail.strip():
        lines.append(element.tail.strip())
    return lines


class JSONXMLParser(BaseParser):
    supported_extensions = [".json", ".xml"]
    supported_mime_types = ["application/json", "text/xml", "application/xml"]

    def parse(self, content: bytes, filename: str) -> ParsedDocument:
        text_lines: list[str] = []
        if filename.lower().endswith(".json"):
            try:
                data = json.loads(content.decode("utf-8", errors="replace"))
                text_lines = _flatten_json(data)
            except json.JSONDecodeError as e:
                text_lines = [f"JSON parse error: {e}", content.decode("utf-8", errors="replace")[:2000]]
        else:
            try:
                root = ET.fromstring(content.decode("utf-8", errors="replace"))
                text_lines = _extract_xml_text(root)
            except ET.ParseError as e:
                text_lines = [f"XML parse error: {e}"]
        full_text = "\n".join(text_lines)
        return ParsedDocument(
            text=full_text,
            page_count=1,
            metadata={"filename": filename},
        )
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/test_parsers_new.py -v
```

- [ ] **Step 5: Register in factory**

```python
from ingestion.parsers.json_xml_parser import JSONXMLParser
for cls in (PDFParser, DOCXParser, TXTParser, CSVParser, PPTXParser, HTMLParser, JSONXMLParser):
```

- [ ] **Step 6: Commit**

```bash
git add ingestion/parsers/json_xml_parser.py ingestion/parsers/factory.py tests/test_parsers_new.py
git commit -m "feat: add JSON/XML parser with recursive text flattening"
```

---

### Task 1.6: DB migration — add session_id to Conversation

**Files:**
- Modify: `models/db.py`
- Create: `alembic/versions/002_add_session_id_audit_tables.py`

- [ ] **Step 1: Add `session_id` column to `Conversation` in `models/db.py`**

```python
class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), default="local")
    session_id: Mapped[str] = mapped_column(String(64), index=True, default="")  # NEW
    messages_json: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 2: Add the 3 audit tables to `models/db.py`**

```python
from sqlalchemy import Date, Float

class QueryLog(Base):
    __tablename__ = "query_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    session_id: Mapped[str] = mapped_column(String(64), default="")
    query_text: Mapped[str] = mapped_column(Text)
    model_used: Mapped[str] = mapped_column(String(128), default="")
    model_tier: Mapped[str] = mapped_column(String(16), default="")
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    cache_tier_hit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    confidence: Mapped[str] = mapped_column(String(8), default="")
    fallback_tier: Mapped[str | None] = mapped_column(String(16), nullable=True)
    chunks_retrieved: Mapped[int] = mapped_column(Integer, default=0)


class TokenUsage(Base):
    __tablename__ = "token_usage"
    __table_args__ = (UniqueConstraint("date", name="uq_token_usage_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[datetime] = mapped_column(Date, index=True)
    tier_1_tokens: Mapped[int] = mapped_column(Integer, default=0)
    tier_2_tokens: Mapped[int] = mapped_column(Integer, default=0)
    tier_3_tokens: Mapped[int] = mapped_column(Integer, default=0)
    tier_1_cost: Mapped[float] = mapped_column(Float, default=0.0)
    tier_2_cost: Mapped[float] = mapped_column(Float, default=0.0)
    tier_3_cost: Mapped[float] = mapped_column(Float, default=0.0)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)


class IngestionLog(Base):
    __tablename__ = "ingestion_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String(64), ForeignKey("documents.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(16))  # "success" | "failed" | "duplicate"
    chunks_created: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Replace the existing `from sqlalchemy import ...` line (line 9) with:
```python
from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
```

- [ ] **Step 3: Generate Alembic migration**

```bash
alembic revision --autogenerate -m "add_session_id_and_audit_tables"
```

- [ ] **Step 4: Apply migration**

```bash
alembic upgrade head
```

- [ ] **Step 5: Verify tables exist**

```bash
python -c "
from models.session import get_db
from models.db import QueryLog, TokenUsage, IngestionLog, Conversation
with get_db() as db:
    print('QueryLog columns:', [c.name for c in QueryLog.__table__.columns])
    print('Conversation columns:', [c.name for c in Conversation.__table__.columns])
"
```
Expected: `session_id` in Conversation columns, all 3 new tables listed.

- [ ] **Step 6: Commit**

```bash
git add models/db.py alembic/versions/
git commit -m "feat: add session_id to Conversation; add QueryLog, TokenUsage, IngestionLog tables"
```

---

### Task 1.7: Run full test suite — Sprint 1 checkpoint

- [ ] **Step 1: Run all tests**

```bash
pytest -v --tb=short
```

Expected: all existing tests pass + new parser/protocol tests pass. No failures.

- [ ] **Step 2: Commit any fixes discovered**

```bash
git add -p
git commit -m "fix: sprint 1 test suite cleanup"
```

---

## Sprint 2 — Core RAG Loop (Single Model)

### Task 2.1: Shared schemas

**Files:**
- Create: `core/schemas.py`
- Create: `tests/test_schemas.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_schemas.py
from core.schemas import RetrievedChunk, QueryResult

def test_retrieved_chunk_fields():
    chunk = RetrievedChunk(
        text="Sample text",
        doc_name="report.pdf",
        page_number=3,
        chunk_index=0,
        score=0.85,
    )
    assert chunk.score == 0.85
    assert chunk.doc_name == "report.pdf"

def test_query_result_cache_none_by_default():
    chunk = RetrievedChunk(text="t", doc_name="d", page_number=1, chunk_index=0, score=0.8)
    result = QueryResult(
        answer="The answer",
        sources=[chunk],
        model_used="meta-llama/llama-3.1-8b-instruct:free",
        model_tier="SIMPLE",
        tokens_in=100,
        tokens_out=50,
        cost_usd=0.0,
        latency_ms=1200,
        cache_tier_hit=None,
        confidence="HIGH",
        fallback_tier=None,
    )
    assert result.cache_tier_hit is None
    assert len(result.sources) == 1
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_schemas.py -v
```

- [ ] **Step 3: Create `core/schemas.py`**

```python
"""Shared dataclasses used across the RAG pipeline."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class RetrievedChunk:
    text: str
    doc_name: str
    page_number: int | None
    chunk_index: int
    score: float  # cosine similarity 0–1


@dataclass
class QueryResult:
    answer: str
    sources: list[RetrievedChunk]
    model_used: str
    model_tier: str        # "SIMPLE" | "MODERATE" | "COMPLEX"
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    cache_tier_hit: str | None   # "TIER_1" | "TIER_2" | None
    confidence: str        # "LOW" | "MEDIUM" | "HIGH"
    fallback_tier: str | None = None
    chunks_retrieved: int = field(init=False)

    def __post_init__(self) -> None:
        self.chunks_retrieved = len(self.sources)
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/test_schemas.py -v
```

- [ ] **Step 5: Commit**

```bash
git add core/schemas.py tests/test_schemas.py
git commit -m "feat: add shared RAG pipeline dataclasses (RetrievedChunk, QueryResult)"
```

---

### Task 2.2: Confidence scorer

**Files:**
- Create: `core/confidence.py`
- Create: `tests/test_confidence.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_confidence.py
from core.schemas import RetrievedChunk
from core.confidence import score_confidence

def _chunk(s: float) -> RetrievedChunk:
    return RetrievedChunk(text="t", doc_name="d", page_number=1, chunk_index=0, score=s)

def test_high_confidence():
    chunks = [_chunk(0.85), _chunk(0.90), _chunk(0.82)]
    assert score_confidence(chunks) == "HIGH"

def test_medium_confidence_by_score():
    chunks = [_chunk(0.70), _chunk(0.68)]
    assert score_confidence(chunks) == "MEDIUM"

def test_medium_confidence_by_count():
    chunks = [_chunk(0.60), _chunk(0.61)]  # avg < 0.65 but count >= 2
    assert score_confidence(chunks) == "MEDIUM"

def test_low_confidence_single_weak_chunk():
    chunks = [_chunk(0.55)]
    assert score_confidence(chunks) == "LOW"

def test_low_confidence_empty():
    assert score_confidence([]) == "LOW"
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_confidence.py -v
```

- [ ] **Step 3: Create `core/confidence.py`**

```python
"""Confidence scoring: retrieval signals → LOW / MEDIUM / HIGH label."""
from __future__ import annotations
from core.schemas import RetrievedChunk


def score_confidence(chunks: list[RetrievedChunk]) -> str:
    """
    HIGH:   avg similarity >= 0.80 AND chunk count >= 3
    MEDIUM: avg similarity >= 0.65 OR chunk count >= 2
    LOW:    otherwise (single weak chunk or no chunks)
    """
    if not chunks:
        return "LOW"
    avg = sum(c.score for c in chunks) / len(chunks)
    if avg >= 0.80 and len(chunks) >= 3:
        return "HIGH"
    if avg >= 0.65 or len(chunks) >= 2:
        return "MEDIUM"
    return "LOW"
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/test_confidence.py -v
```

- [ ] **Step 5: Commit**

```bash
git add core/confidence.py tests/test_confidence.py
git commit -m "feat: add confidence scorer (retrieval signals → LOW/MEDIUM/HIGH)"
```

---

### Task 2.3: Prompt builder

**Files:**
- Create: `core/prompt_builder.py`
- Create: `tests/test_prompt_builder.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_prompt_builder.py
from core.schemas import RetrievedChunk
from core.prompt_builder import build_messages

def _chunk(text: str, doc: str = "report.pdf", page: int = 1) -> RetrievedChunk:
    return RetrievedChunk(text=text, doc_name=doc, page_number=page, chunk_index=0, score=0.8)

def test_messages_list_structure():
    chunks = [_chunk("The deadline is Q3.")]
    msgs = build_messages("When is the deadline?", chunks, history=[])
    roles = [m["role"] for m in msgs]
    assert roles[0] == "system"
    assert roles[-1] == "user"

def test_source_context_in_user_message():
    chunks = [_chunk("Revenue was $10M.", "finance.pdf", 4)]
    msgs = build_messages("What was revenue?", chunks, history=[])
    combined = " ".join(m["content"] for m in msgs)
    assert "[Source 1]" in combined
    assert "finance.pdf" in combined
    assert "Revenue was $10M" in combined

def test_conversation_history_included():
    chunks = [_chunk("text")]
    history = [
        {"role": "user", "content": "First question"},
        {"role": "assistant", "content": "First answer"},
    ]
    msgs = build_messages("Follow-up", chunks, history=history)
    contents = [m["content"] for m in msgs]
    assert any("First question" in c for c in contents)

def test_no_sources_triggers_fallback_instruction():
    msgs = build_messages("Who are you?", chunks=[], history=[])
    system_content = msgs[0]["content"]
    assert "don't have enough information" in system_content.lower() or "i don't know" in system_content.lower()
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_prompt_builder.py -v
```

- [ ] **Step 3: Create `core/prompt_builder.py`**

```python
"""Prompt builder: assembles messages list for OpenRouter/OpenAI chat format."""
from __future__ import annotations
from core.schemas import RetrievedChunk

SYSTEM_PROMPT = """You are IntelRAG, an enterprise knowledge assistant.
Answer questions using ONLY the context provided below.
- Cite sources inline as [Source N] and list references at the end.
- If the context is insufficient, respond: "I don't have enough information in the indexed documents to answer this."
- Never invent facts. Be concise and professional."""


def build_messages(
    query: str,
    chunks: list[RetrievedChunk],
    history: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Return a messages list in OpenAI chat format."""
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    if chunks:
        source_blocks = "\n\n".join(
            f"[Source {i + 1}] {c.doc_name}"
            + (f", page {c.page_number}" if c.page_number else "")
            + f":\n{c.text}"
            for i, c in enumerate(chunks)
        )
        context_msg = f"CONTEXT:\n{source_blocks}"
        messages.append({"role": "system", "content": context_msg})

    # Conversation history (last N turns, already trimmed by caller)
    for turn in history:
        messages.append({"role": turn["role"], "content": turn["content"]})

    messages.append({"role": "user", "content": query})
    return messages
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/test_prompt_builder.py -v
```

- [ ] **Step 5: Commit**

```bash
git add core/prompt_builder.py tests/test_prompt_builder.py
git commit -m "feat: add prompt builder with citation format and conversation history"
```

---

### Task 2.4: Retriever

**Files:**
- Create: `core/retriever.py`
- Create: `tests/test_retriever.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_retriever.py
from unittest.mock import MagicMock, patch
from core.retriever import retrieve_chunks
from core.schemas import RetrievedChunk

def _make_chroma_response(scores, texts, metadatas):
    """Build a ChromaDB-style search result dict."""
    return {
        "ids": [[f"id_{i}" for i in range(len(scores))]],
        "distances": [scores],
        "documents": [texts],
        "metadatas": [metadatas],
    }

def test_retrieve_filters_below_threshold():
    mock_vs = MagicMock()
    mock_vs.search.return_value = _make_chroma_response(
        scores=[0.3, 0.8, 0.6],   # ChromaDB cosine distance: lower = more similar
        texts=["low sim", "high sim", "medium sim"],
        metadatas=[
            {"doc_id": "d1", "source_file": "a.pdf", "page_number": 1, "chunk_index": 0},
            {"doc_id": "d1", "source_file": "a.pdf", "page_number": 2, "chunk_index": 1},
            {"doc_id": "d1", "source_file": "a.pdf", "page_number": 3, "chunk_index": 2},
        ],
    )
    mock_cache = MagicMock()
    mock_cache.get_embedding.return_value = None
    mock_embed = MagicMock(return_value=[[0.1] * 384])

    with patch("core.retriever.embed_texts", mock_embed):
        chunks = retrieve_chunks("test query", mock_vs, mock_cache)

    # distance 0.3 → similarity 0.7 (boundary), 0.8 → 0.2 (drop), 0.6 → 0.4 (drop)
    # Only chunks with (1 - distance) >= threshold=0.7 should pass
    assert all(c.score >= 0.7 for c in chunks)

def test_retrieve_returns_retrieved_chunks():
    mock_vs = MagicMock()
    mock_vs.search.return_value = _make_chroma_response(
        scores=[0.1, 0.15],
        texts=["First chunk", "Second chunk"],
        metadatas=[
            {"doc_id": "d1", "source_file": "doc.pdf", "page_number": 1, "chunk_index": 0},
            {"doc_id": "d1", "source_file": "doc.pdf", "page_number": 2, "chunk_index": 1},
        ],
    )
    mock_cache = MagicMock()
    mock_cache.get_embedding.return_value = None
    mock_embed = MagicMock(return_value=[[0.1] * 384])

    with patch("core.retriever.embed_texts", mock_embed):
        chunks = retrieve_chunks("query", mock_vs, mock_cache)

    assert len(chunks) == 2
    assert isinstance(chunks[0], RetrievedChunk)
    assert chunks[0].doc_name == "doc.pdf"
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_retriever.py -v
```

- [ ] **Step 3: Create `core/retriever.py`**

```python
"""RAG retriever: embed query → vector search → filter → deduplicate → assemble context."""
from __future__ import annotations
from core.embedding_service import embed_texts
from core.schemas import RetrievedChunk
from config.settings import get_settings


def retrieve_chunks(
    query: str,
    vector_store,
    cache_manager,
    top_k: int | None = None,
    top_k_rerank: int | None = None,
    threshold: float | None = None,
) -> list[RetrievedChunk]:
    """
    1. Get query embedding (Tier 3 cache → compute if miss)
    2. Search vector store top_k candidates
    3. Convert ChromaDB distances to similarity scores (sim = 1 - dist)
    4. Filter below threshold
    5. Deduplicate adjacent chunks from same doc
    6. Return top_k_rerank results ordered by score desc
    """
    settings = get_settings()
    top_k = top_k or settings.top_k_retrieval
    top_k_rerank = top_k_rerank or settings.top_k_rerank
    threshold = threshold if threshold is not None else settings.similarity_threshold

    # Tier 3 embedding cache
    embedding = cache_manager.get_embedding(query, settings.embedding_model)
    if embedding is None:
        embedding = embed_texts([query])[0]
        cache_manager.store_embedding(query, settings.embedding_model, embedding)

    count = vector_store.count()
    if count == 0:
        return []

    results = vector_store.search(
        query_embeddings=[embedding],
        n_results=min(top_k, count),
    )

    ids = results.get("ids", [[]])[0]
    distances = results.get("distances", [[]])[0]
    texts = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    chunks: list[RetrievedChunk] = []
    for i, (dist, text, meta) in enumerate(zip(distances, texts, metadatas)):
        similarity = 1.0 - float(dist)  # ChromaDB cosine distance → similarity
        if similarity < threshold:
            continue
        chunks.append(
            RetrievedChunk(
                text=text or "",
                doc_name=meta.get("source_file", "unknown"),
                page_number=int(meta.get("page_number", 0)) or None,
                chunk_index=int(meta.get("chunk_index", i)),
                score=round(similarity, 4),
            )
        )

    # Deduplicate: drop adjacent chunks from same doc (chunk_index differing by 1)
    chunks = _deduplicate(chunks)

    # Order by score descending, take top_k_rerank
    chunks.sort(key=lambda c: c.score, reverse=True)
    return chunks[:top_k_rerank]


def _deduplicate(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Remove chunks that are adjacent to a higher-scoring chunk from the same doc."""
    seen: set[tuple[str, int]] = set()
    result: list[RetrievedChunk] = []
    for chunk in sorted(chunks, key=lambda c: c.score, reverse=True):
        key = (chunk.doc_name, chunk.chunk_index)
        adjacent = (chunk.doc_name, chunk.chunk_index - 1) in seen or \
                   (chunk.doc_name, chunk.chunk_index + 1) in seen
        if not adjacent:
            result.append(chunk)
            seen.add(key)
    return result
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/test_retriever.py -v
```

- [ ] **Step 5: Commit**

```bash
git add core/retriever.py tests/test_retriever.py
git commit -m "feat: add RAG retriever with similarity filter, dedup, and Tier 3 cache integration"
```

---

### Task 2.5: LLM service (single model, no routing yet)

**Files:**
- Create: `core/llm_service.py`
- Create: `tests/test_llm_service.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_llm_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

def test_llm_unavailable_error_importable():
    from core.llm_service import LLMUnavailableError
    assert issubclass(LLMUnavailableError, Exception)

def test_estimate_cost_free_model():
    from core.llm_service import estimate_cost
    cost = estimate_cost("meta-llama/llama-3.1-8b-instruct:free", 1000, 500)
    assert cost == 0.0

def test_estimate_cost_paid_model():
    from core.llm_service import estimate_cost
    cost = estimate_cost("openai/gpt-4o-mini", 1_000_000, 0)
    assert cost == pytest.approx(0.15, rel=0.01)

def test_get_client_not_none():
    from core.llm_service import get_openrouter_client
    import os
    os.environ["OPENROUTER_API_KEY"] = "test-key"
    client = get_openrouter_client()
    assert client is not None
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_llm_service.py -v
```

- [ ] **Step 3: Create `core/llm_service.py`**

```python
"""
LLM service: OpenRouter client, streaming, retry+backoff, token capture.
Fallback chain handled by complexity_classifier (Sprint 3).
"""
from __future__ import annotations
import asyncio
import random
import time
from typing import AsyncGenerator, Generator

import openai

from config.logging_config import get_logger
from config.settings import get_settings

logger = get_logger(__name__)

# Cost per 1M tokens (prompt + completion combined)
MODEL_PRICES: dict[str, float] = {
    "meta-llama/llama-3.1-8b-instruct:free": 0.0,
    "mistralai/mistral-7b-instruct:free": 0.0,
    "google/gemma-2-9b-it:free": 0.0,
    "google/gemini-2.0-flash-exp:free": 0.0,
    "google/gemini-2.0-flash": 0.10,
    "openai/gpt-4o-mini": 0.15,
    "openai/gpt-4o": 5.00,
}


class LLMUnavailableError(Exception):
    """Raised when all retry attempts and fallback tiers are exhausted."""


def estimate_cost(model_id: str, tokens_in: int, tokens_out: int) -> float:
    price_per_1m = MODEL_PRICES.get(model_id, 0.50)  # default to mid-tier if unknown
    return (tokens_in + tokens_out) * price_per_1m / 1_000_000


def get_openrouter_client() -> openai.OpenAI:
    s = get_settings()
    return openai.OpenAI(
        base_url=s.openrouter_base_url,
        api_key=s.openrouter_api_key,
        default_headers={
            "HTTP-Referer": s.openrouter_http_referer,
            "X-Title": s.openrouter_x_title,
        },
        timeout=s.llm_timeout_seconds,
    )


def _should_retry(exc: Exception) -> bool:
    """Retry on server errors and timeouts, NOT on 4xx client errors."""
    if isinstance(exc, openai.APIStatusError):
        return exc.status_code >= 500
    if isinstance(exc, (openai.APIConnectionError, openai.APITimeoutError)):
        return True
    return False


def call_llm(
    messages: list[dict[str, str]],
    model_id: str,
) -> tuple[str, int, int, float]:
    """
    Non-streaming LLM call with retry + backoff.
    Returns (answer, tokens_in, tokens_out, cost_usd).
    Raises LLMUnavailableError after all retries exhausted.
    """
    s = get_settings()
    client = get_openrouter_client()
    last_exc: Exception | None = None

    for attempt in range(s.llm_max_retries):
        if attempt > 0:
            delay = s.llm_retry_base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            logger.warning("llm_retry", attempt=attempt, model=model_id, delay=round(delay, 2))
            time.sleep(delay)
        try:
            response = client.chat.completions.create(
                model=model_id,
                messages=messages,  # type: ignore[arg-type]
                stream=False,
            )
            answer = response.choices[0].message.content or ""
            tokens_in = response.usage.prompt_tokens if response.usage else 0
            tokens_out = response.usage.completion_tokens if response.usage else 0
            cost = estimate_cost(model_id, tokens_in, tokens_out)
            logger.info("llm_success", model=model_id, tokens_in=tokens_in, tokens_out=tokens_out)
            return answer, tokens_in, tokens_out, cost
        except Exception as exc:
            last_exc = exc
            if not _should_retry(exc):
                break
            logger.warning("llm_attempt_failed", attempt=attempt, model=model_id, error=str(exc))

    raise LLMUnavailableError(f"LLM call failed after {s.llm_max_retries} attempts: {last_exc}") from last_exc


def stream_llm(
    messages: list[dict[str, str]],
    model_id: str,
) -> Generator[str, None, None]:
    """
    Streaming LLM call. Yields token strings one at a time.
    Token counts are not captured from streaming responses — use call_llm() for
    accurate token/cost tracking. This is used for Streamlit live token rendering only.
    """
    s = get_settings()
    client = get_openrouter_client()
    last_exc: Exception | None = None

    for attempt in range(s.llm_max_retries):
        if attempt > 0:
            delay = s.llm_retry_base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            time.sleep(delay)
        try:
            with client.chat.completions.create(
                model=model_id,
                messages=messages,  # type: ignore[arg-type]
                stream=True,
            ) as stream:
                full_text = ""
                for chunk in stream:
                    delta = chunk.choices[0].delta.content or ""
                    full_text += delta
                    yield delta
                # Usage is in the final chunk for some providers
                return
        except Exception as exc:
            last_exc = exc
            if not _should_retry(exc):
                break

    raise LLMUnavailableError(f"Streaming LLM failed: {last_exc}") from last_exc
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/test_llm_service.py -v
```

- [ ] **Step 5: Commit**

```bash
git add core/llm_service.py tests/test_llm_service.py
git commit -m "feat: add LLM service with OpenRouter client, retry+backoff, cost estimation"
```

---

### Task 2.6: Stub cache manager (needed before wiring chat.py)

**Files:**
- Create: `core/cache/__init__.py`
- Create: `core/cache/redis_client.py`
- Create: `core/cache/cache_manager.py` (stub — full implementation in Sprint 4)

- [ ] **Step 1: Create `core/cache/__init__.py`** (empty)

- [ ] **Step 2: Create `core/cache/redis_client.py`**

```python
"""
Redis client wrapper. Uses fakeredis in dev/test; real Redis when REDIS_URL is set.
Swap to real Redis: set REDIS_URL=redis://host:6379/0 in .env.
"""
from __future__ import annotations
import fakeredis
import redis as redis_lib
from config.settings import get_settings

_client: redis_lib.Redis | fakeredis.FakeRedis | None = None


def get_redis() -> redis_lib.Redis | fakeredis.FakeRedis:
    global _client
    if _client is None:
        s = get_settings()
        # Use real Redis only when explicitly configured AND not in dev/test environment
        use_real = (
            s.redis_url
            and s.redis_url.startswith("redis://")
            and s.environment not in ("development", "test")
        )
        if use_real:
            _client = redis_lib.from_url(s.redis_url, decode_responses=False)
        else:
            _client = fakeredis.FakeRedis()
    return _client


def reset_client() -> None:
    """Force re-initialisation (useful in tests)."""
    global _client
    _client = None
```

- [ ] **Step 2b: Write stub interface test**

```python
# tests/test_cache_stub.py
def test_cache_manager_stub_lookup_returns_none():
    from core.cache.cache_manager import get_cache_manager
    cm = get_cache_manager()
    assert cm.lookup("any query", "any_hash", "any_model") is None

def test_cache_manager_stub_get_embedding_returns_none():
    from core.cache.cache_manager import get_cache_manager
    cm = get_cache_manager()
    assert cm.get_embedding("text", "model") is None
```

Run: `pytest tests/test_cache_stub.py -v`
Expected: FAIL (module not created yet)

- [ ] **Step 3: Create stub `core/cache/cache_manager.py`**

```python
"""
Cache manager: 3-tier cache (Tier 1 exact, Tier 2 semantic, Tier 3 embedding).
Sprint 4 implements all tiers. This stub provides the interface so Sprint 2/3 can call it.
"""
from __future__ import annotations
from core.schemas import QueryResult


class CacheManager:
    """
    Stub — all methods are no-ops until Sprint 4 fills them in.
    Interface is stable so callers don't need to change in Sprint 4.
    """

    def lookup(self, query: str, doc_set_hash: str, model_id: str) -> QueryResult | None:
        return None

    def store(self, query: str, doc_set_hash: str, model_id: str, result: QueryResult) -> None:
        pass

    def get_embedding(self, text: str, model_name: str) -> list[float] | None:
        return None

    def store_embedding(self, text: str, model_name: str, embedding: list[float]) -> None:
        pass

    def invalidate_on_doc_change(self) -> None:
        pass

    def get_stats(self) -> dict[str, int]:
        return {"tier1_hits": 0, "tier2_hits": 0, "tier3_hits": 0, "misses": 0}


# Module-level singleton
_manager: CacheManager | None = None


def get_cache_manager() -> CacheManager:
    global _manager
    if _manager is None:
        _manager = CacheManager()
    return _manager
```

- [ ] **Step 4: Commit**

```bash
git add core/cache/
git commit -m "feat: add Redis client wrapper and CacheManager stub for Sprint 2 wiring"
```

---

### Task 2.7: Wire single-model RAG into chat.py

**Files:**
- Modify: `app/pages/chat.py`

- [ ] **Step 1: Rewrite `app/pages/chat.py`** with full single-model RAG loop

```python
"""
Chat page: single-model RAG loop (Sprint 2).
Sprint 3 adds complexity routing. Sprint 5 adds multi-turn persistence.
"""
from __future__ import annotations
import time
import uuid
from datetime import datetime

import streamlit as st

from config.settings import get_settings
from core.cache.cache_manager import get_cache_manager
from core.confidence import score_confidence
from core.prompt_builder import build_messages
from core.retriever import retrieve_chunks
from core.llm_service import call_llm, LLMUnavailableError
from core.storage.vector_store import VectorStore

st.set_page_config(page_title="IntelRAG — Chat", layout="wide")


def _init_session() -> None:
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())
    if "messages" not in st.session_state:
        st.session_state["messages"] = []


def _render_message(role: str, content: str, meta: dict | None = None) -> None:
    with st.chat_message(role):
        st.markdown(content)
        if meta and role == "assistant":
            cols = st.columns(3)
            cols[0].markdown(f"**Cache:** {meta.get('cache', '🆕 Fresh')}")
            cols[1].markdown(f"**Model:** {meta.get('model_short', '—')}")
            cols[2].markdown(f"**Confidence:** {meta.get('confidence', '—')}")
            if meta.get("sources"):
                with st.expander("📎 Sources", expanded=False):
                    for i, src in enumerate(meta["sources"], 1):
                        pg = f", page {src['page']}" if src.get("page") else ""
                        st.markdown(f"**[Source {i}]** `{src['doc_name']}`{pg} (score: {src['score']:.2f})")
                        st.caption(src["text"][:300] + ("…" if len(src["text"]) > 300 else ""))


def main() -> None:
    _init_session()
    s = get_settings()
    st.title("💬 IntelRAG Chat")

    # Sidebar controls
    with st.sidebar:
        st.header("Session")
        if st.button("🆕 New Conversation"):
            st.session_state["messages"] = []
            st.session_state["session_id"] = str(uuid.uuid4())
            st.rerun()
        st.caption(f"Session: `{st.session_state['session_id'][:8]}…`")

    # Render history
    for msg in st.session_state["messages"]:
        _render_message(msg["role"], msg["content"], msg.get("meta"))

    # Input
    if prompt := st.chat_input("Ask a question about your documents…"):
        st.session_state["messages"].append({"role": "user", "content": prompt})
        _render_message("user", prompt)

        with st.spinner("Thinking…"):
            try:
                t0 = time.time()
                cache_mgr = get_cache_manager()
                vs = VectorStore()

                # Retrieval
                chunks = retrieve_chunks(prompt, vs, cache_mgr)
                if not chunks:
                    answer = "I don't have enough information in the indexed documents to answer this."
                    sources_meta = []
                    confidence = "LOW"
                    model_used = "—"
                    model_short = "—"
                    tokens_in = tokens_out = 0
                    cost = 0.0
                else:
                    # Build prompt (single-turn for Sprint 2)
                    messages = build_messages(prompt, chunks, history=[])
                    model_id = s.tier_1_model  # fixed in Sprint 2; routing added in Sprint 3

                    answer, tokens_in, tokens_out, cost = call_llm(messages, model_id)
                    confidence = score_confidence(chunks)
                    model_short = model_id.split("/")[-1]
                    sources_meta = [
                        {"doc_name": c.doc_name, "page": c.page_number,
                         "text": c.text, "score": c.score}
                        for c in chunks
                    ]

                latency_ms = int((time.time() - t0) * 1000)
                meta = {
                    "cache": "🆕 Fresh",
                    "model_short": model_short,
                    "confidence": f"{'🟢' if confidence == 'HIGH' else '🟡' if confidence == 'MEDIUM' else '🔴'} {confidence}",
                    "sources": sources_meta,
                }
                st.session_state["messages"].append(
                    {"role": "assistant", "content": answer, "meta": meta}
                )
                _render_message("assistant", answer, meta)

            except LLMUnavailableError as e:
                err = f"⚠️ LLM unavailable: {e}"
                st.error(err)
                st.session_state["messages"].append({"role": "assistant", "content": err})
            except Exception as e:
                err = f"⚠️ Unexpected error: {e}"
                st.error(err)


main()
```

- [ ] **Step 2: Start the app and test manually**

```bash
streamlit run app/main.py
```

1. Upload a PDF on the Documents page
2. Go to Chat — ask "What is this document about?"
3. Expected: an answer appears with sources, Fresh badge, and confidence badge

- [ ] **Step 3: Commit**

```bash
git add app/pages/chat.py
git commit -m "feat: wire single-model RAG loop into chat.py (Sprint 2 checkpoint)"
```

---

## Sprint 3 — Complexity Classifier + Model Routing

### Task 3.1: Complexity classifier

**Files:**
- Create: `core/complexity_classifier.py`
- Create: `tests/test_complexity_classifier.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_complexity_classifier.py
from core.complexity_classifier import classify, Tier

def test_simple_short_what_is():
    tier, model = classify("What is the SLA?", turn_count=0)
    assert tier == Tier.SIMPLE

def test_complex_compare_keyword():
    tier, model = classify("Compare the pricing models across all three proposals", turn_count=0)
    assert tier == Tier.COMPLEX

def test_moderate_summarize_keyword():
    tier, model = classify("Summarize the key findings of the Q3 report", turn_count=0)
    assert tier == Tier.MODERATE

def test_deep_conversation_escalates():
    tier, _ = classify("What else?", turn_count=5)
    assert tier == Tier.COMPLEX

def test_long_query_defaults_complex():
    long = " ".join(["word"] * 50)
    tier, _ = classify(long, turn_count=0)
    assert tier == Tier.COMPLEX

def test_model_id_matches_tier(monkeypatch):
    from config.settings import get_settings
    s = get_settings()
    _, model = classify("Who is the author?", turn_count=0)
    assert model == s.tier_1_model
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_complexity_classifier.py -v
```

- [ ] **Step 3: Create `core/complexity_classifier.py`**

```python
"""
Query complexity classifier: rule-based, ~5ms.
Returns (Tier, model_id_string).
"""
from __future__ import annotations
from enum import Enum
from config.settings import get_settings

COMPLEX_KEYWORDS  = {"compare", "contrast", "synthesize", "recommend",
                     "evaluate", "contradict", "analyze", "assess", "critique",
                     "differentiate", "reconcile"}
MODERATE_KEYWORDS = {"summarize", "explain", "describe", "outline",
                     "overview", "elaborate", "discuss", "review"}
SIMPLE_KEYWORDS   = {"define", "what", "who", "when", "where", "list",
                     "name", "how many", "count", "show"}


class Tier(str, Enum):
    SIMPLE   = "SIMPLE"
    MODERATE = "MODERATE"
    COMPLEX  = "COMPLEX"


def classify(
    query: str,
    turn_count: int,
    retrieved_doc_count: int = 1,
) -> tuple[Tier, str]:
    """
    Returns (Tier, model_id).
    Hard keyword signals take priority over length/depth heuristics.
    """
    s = get_settings()
    tokens = query.lower().split()
    token_set = set(tokens)

    # Hard signals (priority order: Complex > Moderate > Simple)
    if token_set & COMPLEX_KEYWORDS:
        return Tier.COMPLEX, s.tier_3_model
    if token_set & MODERATE_KEYWORDS:
        return Tier.MODERATE, s.tier_2_model
    if token_set & SIMPLE_KEYWORDS and len(tokens) < 20:
        return Tier.SIMPLE, s.tier_1_model

    # Depth / breadth escalation
    if turn_count >= 5 or retrieved_doc_count >= 4:
        return Tier.COMPLEX, s.tier_3_model
    if turn_count >= 3 or retrieved_doc_count >= 2:
        return Tier.MODERATE, s.tier_2_model

    # Length fallback
    if len(tokens) < 15:
        return Tier.SIMPLE, s.tier_1_model
    if len(tokens) < 40:
        return Tier.MODERATE, s.tier_2_model
    return Tier.COMPLEX, s.tier_3_model
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/test_complexity_classifier.py -v
```

- [ ] **Step 5: Commit**

```bash
git add core/complexity_classifier.py tests/test_complexity_classifier.py
git commit -m "feat: add rule-based complexity classifier with keyword + heuristic routing"
```

---

### Task 3.2: Wire routing + fallback chain into chat.py

**Files:**
- Modify: `app/pages/chat.py`

- [ ] **Step 1: Update the query handler in `chat.py`**

Replace the `model_id = s.tier_1_model` fixed line with:

```python
from core.complexity_classifier import classify, Tier
from core.llm_service import call_llm, LLMUnavailableError

# In the query block, after retrieve_chunks():
tier, model_id = classify(prompt, turn_count=len(st.session_state["messages"]) // 2)

# Fallback chain
fallback_tier = None
FALLBACK_CHAIN = [
    (Tier.SIMPLE,   s.tier_1_model),
    (Tier.MODERATE, s.tier_2_model),
    (Tier.COMPLEX,  s.tier_3_model),
]
start_idx = next(i for i, (t, _) in enumerate(FALLBACK_CHAIN) if t == tier)

answer = tokens_in = tokens_out = cost = None
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
```

Also update the `meta` dict to include tier info:
```python
meta = {
    "cache": "🆕 Fresh",
    "model_short": model_id.split("/")[-1],
    "tier": tier.value,
    "fallback": fallback_tier,
    "confidence": f"{'🟢' if confidence == 'HIGH' else '🟡' if confidence == 'MEDIUM' else '🔴'} {confidence}",
    "sources": sources_meta,
}
```

Update `_render_message` to show the tier badge on the user bubble:
```python
# In render for role == "user", add after content:
if tier := msg.get("tier"):
    st.caption(f"Complexity: **{tier}**")
```

Store tier on user message:
```python
st.session_state["messages"][-1]["tier"] = tier.value  # tag last user message
```

- [ ] **Step 2: Manual test — routing demo**

```bash
streamlit run app/main.py
```

1. Ask "What is the SLA?" → model badge should show Llama 3.1 Free, tier = SIMPLE
2. Ask "Compare all documents and synthesize recommendations" → GPT-4o-mini, COMPLEX
3. Ask "Summarize the key findings" → Gemini Flash, MODERATE

- [ ] **Step 3: Commit**

```bash
git add app/pages/chat.py
git commit -m "feat: add complexity-based model tier routing + fallback chain to chat"
```

---

## Sprint 4 — 3-Tier Caching (fakeredis)

### Task 4.1: Full cache manager implementation

**Files:**
- Modify: `core/cache/cache_manager.py`
- Create: `tests/test_cache_manager.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cache_manager.py
import numpy as np
import pytest
from core.cache.cache_manager import CacheManager
from core.cache.redis_client import reset_client
from core.schemas import QueryResult, RetrievedChunk

@pytest.fixture(autouse=True)
def fresh_redis():
    reset_client()
    # Also reset the CacheManager singleton so it picks up the new FakeRedis instance
    import core.cache.cache_manager as cm_module
    cm_module._manager = None
    yield
    reset_client()
    cm_module._manager = None

def _result(answer: str = "test answer") -> QueryResult:
    chunk = RetrievedChunk(text="ctx", doc_name="doc.pdf", page_number=1, chunk_index=0, score=0.9)
    return QueryResult(
        answer=answer, sources=[chunk],
        model_used="meta-llama/llama-3.1-8b-instruct:free",
        model_tier="SIMPLE", tokens_in=50, tokens_out=30,
        cost_usd=0.0, latency_ms=500,
        cache_tier_hit=None, confidence="HIGH",
    )

# --- Tier 1 ---
def test_tier1_miss_then_hit():
    cm = CacheManager()
    result = cm.lookup("what is X?", "hash1", "model-a")
    assert result is None  # miss

    cm.store("what is X?", "hash1", "model-a", _result())
    hit = cm.lookup("what is X?", "hash1", "model-a")
    assert hit is not None
    assert hit.cache_tier_hit == "TIER_1"

def test_tier1_different_doc_hash_miss():
    cm = CacheManager()
    cm.store("what is X?", "hash1", "model-a", _result())
    result = cm.lookup("what is X?", "hash2", "model-a")  # different corpus
    assert result is None

# --- Tier 3 embedding ---
def test_tier3_store_and_retrieve():
    cm = CacheManager()
    emb = [0.1] * 384
    cm.store_embedding("hello world", "model-v1", emb)
    retrieved = cm.get_embedding("hello world", "model-v1")
    assert retrieved is not None
    assert len(retrieved) == 384
    assert abs(retrieved[0] - 0.1) < 0.001

def test_tier3_miss_returns_none():
    cm = CacheManager()
    result = cm.get_embedding("nonexistent text", "model-v1")
    assert result is None

# --- Invalidation ---
def test_invalidation_clears_tier1():
    cm = CacheManager()
    cm.store("query", "hash1", "model-a", _result())
    cm.invalidate_on_doc_change()
    result = cm.lookup("query", "hash1", "model-a")
    assert result is None

# --- Stats ---
def test_stats_track_hits():
    cm = CacheManager()
    cm.store("q", "h", "m", _result())
    cm.lookup("q", "h", "m")  # hit
    cm.lookup("other", "h", "m")  # miss
    stats = cm.get_stats()
    assert stats["tier1_hits"] >= 1
    assert stats["misses"] >= 1
```

- [ ] **Step 2: Run — expect FAIL** (stub returns None everywhere)

```bash
pytest tests/test_cache_manager.py -v
```

- [ ] **Step 3: Implement full `core/cache/cache_manager.py`**

```python
"""
3-tier cache manager using fakeredis (swappable to real Redis).

Tier 1: Exact-match — Redis STRING, key=SHA-256(query+corpus+model), TTL=24h
Tier 2: Semantic    — Redis HASH per entry + SET index, cosine scan, TTL=48h
Tier 3: Embedding   — Redis STRING (binary), key=SHA-256(text+model), no TTL
"""
from __future__ import annotations
import hashlib
import json
import struct
import uuid
from dataclasses import asdict

import numpy as np

from config.settings import get_settings
from config.logging_config import get_logger
from core.cache.redis_client import get_redis
from core.schemas import QueryResult, RetrievedChunk

logger = get_logger(__name__)

# Redis key prefixes
_T1  = "cache:exact:"
_T2  = "cache:semantic:"
_T2I = "cache:semantic:index"
_T3  = "cache:embedding:"
_STATS = "stats:"


def _sha256(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _encode_embedding(emb: list[float]) -> bytes:
    return struct.pack(f"{len(emb)}f", *emb)


def _decode_embedding(data: bytes) -> list[float]:
    n = len(data) // 4
    return list(struct.unpack(f"{n}f", data))


def _cosine(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a, dtype=np.float32), np.array(b, dtype=np.float32)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(np.dot(va, vb) / denom) if denom > 0 else 0.0


def _result_to_json(result: QueryResult) -> str:
    d = {
        "answer": result.answer,
        "sources": [
            {"text": s.text, "doc_name": s.doc_name, "page_number": s.page_number,
             "chunk_index": s.chunk_index, "score": s.score}
            for s in result.sources
        ],
        "model_used": result.model_used,
        "model_tier": result.model_tier,
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
        "cost_usd": result.cost_usd,
        "latency_ms": result.latency_ms,
        "confidence": result.confidence,
        "fallback_tier": result.fallback_tier,
    }
    return json.dumps(d)


def _json_to_result(data: str, cache_tier: str) -> QueryResult:
    d = json.loads(data)
    sources = [
        RetrievedChunk(
            text=s["text"], doc_name=s["doc_name"],
            page_number=s["page_number"], chunk_index=s["chunk_index"], score=s["score"],
        )
        for s in d["sources"]
    ]
    return QueryResult(
        answer=d["answer"], sources=sources,
        model_used=d["model_used"], model_tier=d["model_tier"],
        tokens_in=d["tokens_in"], tokens_out=d["tokens_out"],
        cost_usd=d["cost_usd"], latency_ms=d["latency_ms"],
        cache_tier_hit=cache_tier, confidence=d["confidence"],
        fallback_tier=d.get("fallback_tier"),
    )


class CacheManager:

    def lookup(self, query: str, doc_set_hash: str, model_id: str) -> QueryResult | None:
        r = get_redis()
        s = get_settings()

        # Tier 1 — exact match
        t1_key = _T1 + _sha256(query, doc_set_hash, model_id)
        raw = r.get(t1_key)
        if raw:
            r.incr(_STATS + "tier1_hits")
            logger.debug("cache_tier1_hit", key=t1_key[:20])
            return _json_to_result(raw.decode(), "TIER_1")

        # Tier 2 — semantic scan
        index_members = r.smembers(_T2I)
        if index_members:
            query_emb = self.get_embedding(query, s.embedding_model)
            if query_emb is None:
                from core.embedding_service import embed_texts
                query_emb = embed_texts([query])[0]
            best_score = 0.0
            best_response: str | None = None
            for member in index_members:
                entry_key = _T2 + member.decode()
                if not r.exists(entry_key):
                    r.srem(_T2I, member)
                    continue
                stored_emb_bytes = r.hget(entry_key, "embedding")
                if not stored_emb_bytes:
                    continue
                stored_emb = _decode_embedding(stored_emb_bytes)
                sim = _cosine(query_emb, stored_emb)
                if sim > best_score:
                    best_score = sim
                    best_response = r.hget(entry_key, "response")
                    if best_response:
                        best_response = best_response.decode()
            if best_score >= s.cache_semantic_similarity_threshold and best_response:
                r.incr(_STATS + "tier2_hits")
                logger.debug("cache_tier2_hit", similarity=round(best_score, 3))
                return _json_to_result(best_response, "TIER_2")

        r.incr(_STATS + "misses")
        return None

    def store(self, query: str, doc_set_hash: str, model_id: str, result: QueryResult) -> None:
        r = get_redis()
        s = get_settings()

        # Tier 1
        t1_key = _T1 + _sha256(query, doc_set_hash, model_id)
        r.set(t1_key, _result_to_json(result), ex=s.cache_exact_ttl)

        # Tier 2 — store query embedding + response
        emb = self.get_embedding(query, s.embedding_model)
        if emb is None:
            from core.embedding_service import embed_texts
            emb = embed_texts([query])[0]
            self.store_embedding(query, s.embedding_model, emb)
        entry_id = str(uuid.uuid4())
        entry_key = _T2 + entry_id
        r.hset(entry_key, mapping={
            "embedding": _encode_embedding(emb),
            "response": _result_to_json(result),
        })
        r.expire(entry_key, s.cache_semantic_ttl)
        r.sadd(_T2I, entry_id)

    def get_embedding(self, text: str, model_name: str) -> list[float] | None:
        r = get_redis()
        key = _T3 + _sha256(text, model_name)
        raw = r.get(key)
        if raw:
            return _decode_embedding(raw)
        return None

    def store_embedding(self, text: str, model_name: str, embedding: list[float]) -> None:
        r = get_redis()
        key = _T3 + _sha256(text, model_name)
        r.set(key, _encode_embedding(embedding))  # no TTL — deterministic

    def invalidate_on_doc_change(self) -> None:
        """Flush Tier 1 + Tier 2. Tier 3 (embedding) is preserved."""
        r = get_redis()
        # Tier 1
        for key in r.scan_iter(_T1 + "*"):
            r.delete(key)
        # Tier 2
        for member in r.smembers(_T2I):
            r.delete(_T2 + member.decode())
        r.delete(_T2I)
        logger.info("cache_invalidated", tiers="T1+T2")

    def flush_embedding_cache(self) -> None:
        """Flush Tier 3 on embedding model change."""
        r = get_redis()
        for key in r.scan_iter(_T3 + "*"):
            r.delete(key)

    def get_stats(self) -> dict[str, int]:
        r = get_redis()
        def _get(k: str) -> int:
            v = r.get(_STATS + k)
            return int(v) if v else 0
        return {
            "tier1_hits": _get("tier1_hits"),
            "tier2_hits": _get("tier2_hits"),
            "tier3_hits": _get("tier3_hits"),
            "misses": _get("misses"),
        }


_manager: CacheManager | None = None


def get_cache_manager() -> CacheManager:
    global _manager
    if _manager is None:
        _manager = CacheManager()
    return _manager
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/test_cache_manager.py -v
```

- [ ] **Step 5: Commit**

```bash
git add core/cache/cache_manager.py tests/test_cache_manager.py
git commit -m "feat: implement full 3-tier cache (Tier1 exact, Tier2 semantic, Tier3 embedding) with fakeredis"
```

---

### Task 4.2: Integrate cache into chat.py

**Files:**
- Modify: `app/pages/chat.py`

- [ ] **Step 1: Add `doc_set_hash` computation helper**

Add this utility function to `chat.py`:

```python
def _compute_doc_set_hash() -> str:
    import hashlib
    from models.session import get_db
    from models.db import Document
    with get_db() as db:
        docs = db.query(Document).filter(Document.status == "indexed").all()
        parts = sorted(f"{d.id}:{d.created_at.isoformat()}" for d in docs)
    return hashlib.sha256("|".join(parts).encode()).hexdigest()
```

- [ ] **Step 2: Update the query handler to check cache first**

At the start of the query block (before retrieval), add:

```python
doc_set_hash = _compute_doc_set_hash()
tier, model_id = classify(prompt, turn_count=len(st.session_state["messages"]) // 2)
cache_result = cache_mgr.lookup(prompt, doc_set_hash, model_id)

if cache_result:
    badge = "⚡ Tier 1 Cache Hit" if cache_result.cache_tier_hit == "TIER_1" else "🔮 Tier 2 Semantic Hit"
    meta = {
        "cache": badge,
        "model_short": cache_result.model_used.split("/")[-1],
        "tier": cache_result.model_tier,
        "confidence": f"{'🟢' if cache_result.confidence == 'HIGH' else '🟡' if cache_result.confidence == 'MEDIUM' else '🔴'} {cache_result.confidence}",
        "sources": [{"doc_name": s.doc_name, "page": s.page_number, "text": s.text, "score": s.score} for s in cache_result.sources],
    }
    st.session_state["messages"].append({"role": "assistant", "content": cache_result.answer, "meta": meta})
    _render_message("assistant", cache_result.answer, meta)
    st.stop()
```

After a successful LLM call, store to cache:
```python
cache_mgr.store(prompt, doc_set_hash, model_id, result)
```
where `result` is the `QueryResult` constructed from the LLM response.

- [ ] **Step 3: Update `documents.py` delete to invalidate cache**

In the delete handler in `app/pages/documents.py`:
```python
from core.cache.cache_manager import get_cache_manager
# After deleting from DB + vector store:
get_cache_manager().invalidate_on_doc_change()
```

- [ ] **Step 4: Manual test — cache demo**

```bash
streamlit run app/main.py
```

1. Ask any question → "🆕 Fresh" badge
2. Ask the exact same question → "⚡ Tier 1 Cache Hit" badge, near-instant response
3. Ask a rephrased but semantically identical question → "🔮 Tier 2 Semantic Hit" badge (may not trigger for all rephrasings — that's expected)

- [ ] **Step 5: Commit**

```bash
git add app/pages/chat.py app/pages/documents.py
git commit -m "feat: integrate 3-tier cache into chat (doc_set_hash, cache lookup/store, badge display)"
```

---

## Sprint 5 — Multi-Turn Conversation + SQLite Persistence

### Task 5.1: Load and save conversations to SQLite

**Files:**
- Modify: `app/pages/chat.py`

- [ ] **Step 1: Add conversation persistence helpers to `chat.py`**

```python
import json as _json
from models.session import get_db
from models.db import Conversation

def _load_conversation(session_id: str) -> list[dict]:
    """Load messages from SQLite for this session."""
    with get_db() as db:
        conv = db.query(Conversation).filter(
            Conversation.session_id == session_id
        ).order_by(Conversation.updated_at.desc()).first()
    if conv and conv.messages_json:
        return conv.messages_json if isinstance(conv.messages_json, list) else []
    return []

def _save_conversation(session_id: str, messages: list[dict]) -> None:
    """Upsert conversation to SQLite."""
    import uuid as _uuid
    with get_db() as db:
        conv = db.query(Conversation).filter(
            Conversation.session_id == session_id
        ).first()
        if conv:
            conv.messages_json = messages
        else:
            conv = Conversation(
                id=str(_uuid.uuid4()),
                user_id="local",
                session_id=session_id,
                messages_json=messages,
            )
            db.add(conv)
        db.commit()
```

- [ ] **Step 2: Call load in `_init_session`**

```python
def _init_session() -> None:
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())
    if "messages" not in st.session_state:
        # Try to restore from SQLite
        loaded = _load_conversation(st.session_state["session_id"])
        st.session_state["messages"] = loaded
```

- [ ] **Step 3: Call save after each assistant response**

After appending the assistant message to `st.session_state["messages"]`:
```python
_save_conversation(st.session_state["session_id"], st.session_state["messages"])
```

- [ ] **Step 4: Update "New Conversation" to insert fresh SQLite row**

```python
if st.button("🆕 New Conversation"):
    new_sid = str(uuid.uuid4())
    st.session_state["messages"] = []
    st.session_state["session_id"] = new_sid
    _save_conversation(new_sid, [])
    st.rerun()
```

- [ ] **Step 5: Wire conversation history into prompt builder**

Update the `build_messages` call in the query handler:
```python
s_settings = get_settings()
max_turns = s_settings.conversation_history_turns
# Take last N turns (each turn = 1 user + 1 assistant = 2 messages)
history_msgs = st.session_state["messages"][-(max_turns * 2):-1]
# Filter out metadata — only pass role + content
history = [{"role": m["role"], "content": m["content"]} for m in history_msgs]
messages = build_messages(prompt, chunks, history=history)
```

- [ ] **Step 6: Manual test — persistence demo**

```bash
streamlit run app/main.py
```

1. Ask two questions in a conversation
2. Stop the app (`Ctrl+C`) and restart
3. Navigate to Chat — the history should reload automatically

- [ ] **Step 7: Commit**

```bash
git add app/pages/chat.py
git commit -m "feat: persist conversation history to SQLite, restore on session start"
```

---

## Sprint 6 — Audit Logging

### Task 6.1: Query log + token usage writes

**Files:**
- Create: `core/audit.py`
- Modify: `app/pages/chat.py`
- Modify: `ingestion/pipeline.py`

- [ ] **Step 1: Create `core/audit.py`**

```python
"""Audit log helpers: write QueryLog, TokenUsage, IngestionLog rows."""
from __future__ import annotations
import time
from datetime import date, datetime

from config.logging_config import get_logger
from models.db import IngestionLog, QueryLog, TokenUsage
from models.session import get_db

logger = get_logger(__name__)

TIER_COLUMN = {
    "SIMPLE":   ("tier_1_tokens", "tier_1_cost"),
    "MODERATE": ("tier_2_tokens", "tier_2_cost"),
    "COMPLEX":  ("tier_3_tokens", "tier_3_cost"),
}


def log_query(
    session_id: str,
    query_text: str,
    model_used: str,
    model_tier: str,
    tokens_in: int,
    tokens_out: int,
    cost_usd: float,
    latency_ms: int,
    cache_tier_hit: str | None,
    confidence: str,
    chunks_retrieved: int,
    fallback_tier: str | None = None,
) -> None:
    try:
        with get_db() as db:
            row = QueryLog(
                session_id=session_id,
                query_text=query_text[:2000],
                model_used=model_used,
                model_tier=model_tier,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                cache_tier_hit=cache_tier_hit,
                confidence=confidence,
                chunks_retrieved=chunks_retrieved,
                fallback_tier=fallback_tier,
            )
            db.add(row)
            db.commit()
        _upsert_token_usage(model_tier, tokens_in + tokens_out, cost_usd)
    except Exception as e:
        logger.warning("audit_log_failed", error=str(e))


def _upsert_token_usage(tier: str, total_tokens: int, cost: float) -> None:
    tok_col, cost_col = TIER_COLUMN.get(tier, ("tier_1_tokens", "tier_1_cost"))
    today = date.today()
    try:
        with get_db() as db:
            row = db.query(TokenUsage).filter(TokenUsage.date == today).first()
            if row:
                setattr(row, tok_col, getattr(row, tok_col) + total_tokens)
                setattr(row, cost_col, getattr(row, cost_col) + cost)
                row.total_cost = row.tier_1_cost + row.tier_2_cost + row.tier_3_cost
            else:
                kwargs = {tok_col: total_tokens, cost_col: cost, "total_cost": cost}
                row = TokenUsage(date=today, **kwargs)
                db.add(row)
            db.commit()
    except Exception as e:
        logger.warning("token_usage_upsert_failed", error=str(e))


def log_ingestion(
    document_id: str,
    status: str,
    chunks_created: int = 0,
    duration_ms: int = 0,
    error_message: str | None = None,
) -> None:
    try:
        with get_db() as db:
            row = IngestionLog(
                document_id=document_id,
                status=status,
                chunks_created=chunks_created,
                duration_ms=duration_ms,
                error_message=error_message,
            )
            db.add(row)
            db.commit()
    except Exception as e:
        logger.warning("ingestion_log_failed", error=str(e))
```

- [ ] **Step 2: Call `log_query` in `chat.py`** after successful LLM response:

```python
from core.audit import log_query

log_query(
    session_id=st.session_state["session_id"],
    query_text=prompt,
    model_used=model_id,
    model_tier=tier.value,
    tokens_in=tokens_in,
    tokens_out=tokens_out,
    cost_usd=cost,
    latency_ms=latency_ms,
    cache_tier_hit=None,  # None for fresh responses
    confidence=confidence,
    chunks_retrieved=len(chunks),
    fallback_tier=fallback_tier,
)
```

For cache hits, add this block immediately BEFORE the `st.stop()` call in the cache-hit branch (Task 4.2 Step 2):

```python
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
```

- [ ] **Step 3: Call `log_ingestion` in `ingestion/pipeline.py`**

```python
from core.audit import log_ingestion
import time

# At top of ingest_document, record start time:
t_start = time.time()

# After successful index:
log_ingestion(doc_id, "success", chunks_created=len(chunks),
              duration_ms=int((time.time() - t_start) * 1000))

# In the duplicate branch:
log_ingestion(existing.id, "duplicate")

# In the except block:
log_ingestion(doc_id, "failed", error_message=str(e))
```

- [ ] **Step 4: Verify audit log is populated**

```bash
python -c "
from models.session import get_db
from models.db import QueryLog, IngestionLog
with get_db() as db:
    print('QueryLog rows:', db.query(QueryLog).count())
    print('IngestionLog rows:', db.query(IngestionLog).count())
"
```

- [ ] **Step 5: Commit**

```bash
git add core/audit.py app/pages/chat.py ingestion/pipeline.py
git commit -m "feat: add audit logging (QueryLog, TokenUsage, IngestionLog) wired to chat and ingestion"
```

---

## Sprint 7 — Admin Dashboard + UI Polish (ui-ux-pro-max)

### Task 7.1: Health check module

**Files:**
- Create: `core/health.py`
- Create: `tests/test_health.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_health.py
from core.health import check_all

def test_check_all_returns_dict():
    status = check_all()
    assert isinstance(status, dict)
    assert set(status.keys()) == {"vector_store", "metadata_db", "cache", "openrouter"}

def test_metadata_db_healthy():
    status = check_all()
    assert status["metadata_db"] is True  # SQLite always available locally

def test_cache_healthy():
    status = check_all()
    assert status["cache"] is True  # fakeredis always available
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_health.py -v
```

- [ ] **Step 3: Create `core/health.py`**

```python
"""Health checks for all storage layers and external services."""
from __future__ import annotations
from config.logging_config import get_logger

logger = get_logger(__name__)


def check_all() -> dict[str, bool]:
    return {
        "vector_store": _ping_chromadb(),
        "metadata_db":  _ping_sqlite(),
        "cache":        _ping_cache(),
        "openrouter":   _ping_openrouter(),
    }


def _ping_chromadb() -> bool:
    try:
        from core.storage.vector_store import VectorStore
        vs = VectorStore()
        vs.count()
        return True
    except Exception as e:
        logger.warning("health_chromadb_fail", error=str(e))
        return False


def _ping_sqlite() -> bool:
    try:
        from models.session import get_db
        with get_db() as db:
            db.execute(__import__("sqlalchemy").text("SELECT 1"))
        return True
    except Exception as e:
        logger.warning("health_sqlite_fail", error=str(e))
        return False


def _ping_cache() -> bool:
    try:
        from core.cache.redis_client import get_redis
        r = get_redis()
        r.ping()
        return True
    except Exception as e:
        logger.warning("health_cache_fail", error=str(e))
        return False


def _ping_openrouter() -> bool:
    try:
        import httpx
        from config.settings import get_settings
        s = get_settings()
        r = httpx.head(s.openrouter_base_url, timeout=3.0)
        return r.status_code < 500
    except Exception as e:
        logger.warning("health_openrouter_fail", error=str(e))
        return False
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/test_health.py -v
```

- [ ] **Step 5: Commit**

```bash
git add core/health.py tests/test_health.py
git commit -m "feat: add health check module (ChromaDB, SQLite, cache, OpenRouter)"
```

---

### Task 7.2: Admin dashboard (ui-ux-pro-max)

**Files:**
- Create: `app/pages/admin.py`

- [ ] **Step 1: Invoke ui-ux-pro-max skill for the admin dashboard UI**

> **REQUIRED:** Invoke `ui-ux-pro-max` skill and provide this brief:
>
> Build `app/pages/admin.py` — a Streamlit admin dashboard with:
> - Dark mode, bento-grid layout, professional SaaS aesthetic
> - Row 1: 4 KPI metric cards — Total Queries Today, Cache Hit Rate %, Estimated Cost Saved, Docs Indexed
> - Row 2: Two equal columns — Left: Cost Breakdown per tier (Tier 1 Free/Tier 2 Gemini/Tier 3 OpenAI + total); Right: Cache Performance (hit rate + avg latency per tier)
> - Row 3: Full-width searchable query audit log table (columns: Timestamp, Query, Model, Tier, Tokens, Cost, Cache, Confidence, Latency)
> - Row 4: Health status bar with colored dots (green=up, red=down) for Vector Store, Metadata DB, Cache, OpenRouter
>
> Data sources:
> - `from models.db import QueryLog, TokenUsage, Document`
> - `from models.session import get_db`
> - `from core.cache.cache_manager import get_cache_manager`
> - `from core.health import check_all`

- [ ] **Step 2: Register admin page in `app/main.py`**

Read `app/main.py` and add the Admin page to the navigation. If the app uses `st.navigation` + `st.Page`:

```python
# In app/main.py, add to the pages list:
st.Page("pages/admin.py", title="Admin", icon="⚙️")
```

If it uses sidebar radio/selectbox navigation, add `"Admin"` as an option and a branch that calls `import app.pages.admin`. Check the existing pattern in `app/main.py` and follow it.

- [ ] **Step 3: Manual test — admin dashboard**

```bash
streamlit run app/main.py
```

1. Upload 2 docs, ask 5 queries (mix of fresh + repeated for cache hits)
2. Open Admin dashboard
3. Verify: KPI cards show correct counts, cost breakdown populated, query log shows all 5 rows, health status all green

- [ ] **Step 4: Commit**

```bash
git add app/pages/admin.py app/main.py
git commit -m "feat: add admin dashboard with cost breakdown, cache metrics, audit log, health status"
```

---

### Task 7.3: Document manager polish (ui-ux-pro-max)

**Files:**
- Modify: `app/pages/documents.py`

- [ ] **Step 1: Invoke ui-ux-pro-max skill for document manager polish**

> **REQUIRED:** Invoke `ui-ux-pro-max` skill and provide this brief:
>
> Enhance `app/pages/documents.py` — a Streamlit document management page:
> - Storage indicator at top: Total Docs, Total Chunks, Estimated Vector Store Size (from `vs.count() * 1.5KB` estimate)
> - Sortable/filterable `st.dataframe` table with columns: Name, Type, Size (MB), Pages, Chunks, Upload Date, Status
> - Status badges: Indexed (green), Processing (yellow), Failed (red) using colored markdown/HTML
> - Delete button per row with `st.dialog` confirmation — cascade deletes: file_store + vector_store chunks + metadata DB + `get_cache_manager().invalidate_on_doc_change()`
> - All data from `from models.db import Document` via `get_db()`

- [ ] **Step 2: Manual test**

1. Upload 3 documents
2. Verify sortable table shows all with correct status badges
3. Delete one document — confirm cache invalidation (ask a question about deleted doc → should get "I don't know")

- [ ] **Step 3: Commit**

```bash
git add app/pages/documents.py
git commit -m "feat: polish document manager with sortable table, delete cascade, storage indicator"
```

---

### Task 7.4: Chat UI polish (ui-ux-pro-max)

**Files:**
- Modify: `app/pages/chat.py`

- [ ] **Step 1: Invoke ui-ux-pro-max skill for chat UI polish**

> **REQUIRED:** Invoke `ui-ux-pro-max` skill and provide this brief:
>
> Polish `app/pages/chat.py` — a Streamlit chat interface:
> - Modern chat aesthetic: clean bubbles, readable typography, professional dark/light tone
> - User message bubble: add a small complexity pill badge (SIMPLE/MODERATE/COMPLEX) shown below the message after response arrives
> - Assistant message: cache badge pill above bubble ("⚡ Tier 1 Cache Hit" in green / "🔮 Tier 2 Semantic Hit" in purple / "🆕 Fresh" in gray), model badge, confidence badge (🟢/🟡/🔴)
> - Source panel: expandable `st.expander("📎 N Sources")` showing doc name, page, excerpt, similarity score per chunk
> - Sidebar: session info, New Conversation button, last 5 conversation sessions as clickable history links (query SQLite `Conversation` table)
> - Empty state: friendly illustration/text when no messages yet ("Upload documents and start asking questions")

- [ ] **Step 2: Manual test — full demo flow**

Run through all 9 Done Criteria scenarios from the spec.

- [ ] **Step 3: Commit**

```bash
git add app/pages/chat.py
git commit -m "feat: polish chat UI with complexity badges, streaming, source panel, session history"
```

---

### Task 7.5: Final test suite run

- [ ] **Step 1: Run full test suite**

```bash
pytest -v --tb=short --cov=core --cov=ingestion --cov=models --cov-report=term-missing
```

Expected: all tests pass. Coverage >= 60% on core modules (stretch: 80%).

- [ ] **Step 2: Fix any failures**

Address any broken tests. Do not skip or delete failing tests.

- [ ] **Step 3: Final commit**

```bash
git add .
git commit -m "feat: IntelRAG MVP complete — 7-sprint vertical slice build"
```

---

## Done Criteria Checklist

- [ ] Upload PDF, DOCX, CSV → all indexed with per-file progress badges
- [ ] Upload HTML + PPTX → both indexed and queryable
- [ ] Simple question → SIMPLE badge + Llama Free + 🆕 Fresh + cited sources + confidence badge
- [ ] Same question again → ⚡ Tier 1 Cache Hit badge, < 200ms response
- [ ] Semantically similar rephrase → 🔮 Tier 2 Semantic Hit badge
- [ ] Complex multi-doc question → COMPLEX + GPT-4o-mini badge
- [ ] Follow-up question → context maintained; restart app → history reloads from SQLite
- [ ] Admin dashboard → cost breakdown, cache hit rates, full query log, health all green
- [ ] Delete doc → cache invalidated; doc absent from subsequent query results
