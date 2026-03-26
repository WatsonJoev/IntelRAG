# IntelRAG — MVP Enterprise RAG AI Agent: Design Spec

| Field | Value |
|-------|-------|
| **Date** | 2026-03-26 |
| **Status** | Approved (v2 — post-review fixes applied) |
| **Author** | Joev (via Claude Code brainstorming) |
| **PRD Reference** | PRD.md v1.0 |
| **Build Strategy** | Approach B — Vertical Slice First |

---

## 1. Purpose & Context

IntelRAG is a local-first enterprise RAG (Retrieval-Augmented Generation) platform for POC/prototype use. The goal is an MVP that can be demonstrated to customers and used as a learning vehicle for how real companies implement RAG at scale.

**This spec covers everything required to go from the current Phase 1 (~94% complete) foundation to a fully demo-able, customer-facing MVP.**

The MVP must show:
- Multi-format document ingestion with per-file progress
- Intelligent query routing across 3 LLM tiers based on complexity
- 3-tier caching (exact-match, semantic, embedding) with visible cache hit badges
- Source-cited answers with confidence levels
- Admin dashboard showing live cost breakdown and cache performance

---

## 2. Scope

### In Scope

| Area | Details |
|------|---------|
| Phase 1 gap closure | Vector store abstraction, PPTX/HTML/JSON/XML parsers, metadata extraction, missing unit tests |
| LLM service | OpenRouter client, streaming, exponential backoff retry, token usage capture |
| Complexity classifier | Rule-based (~5ms) — keyword signals, query length, turn depth, doc count |
| Model tier routing | Simple → Free Llama, Moderate → Gemini Flash, Complex → GPT-4o-mini; fallback chain |
| RAG retrieval | Dense vector search, similarity threshold (0.7), context assembly, source metadata |
| RAG generation | Prompt builder with citation format, "I don't know" fallback, multi-turn conversation memory |
| Confidence scoring | Retrieval similarity + chunk count → Low/Medium/High badge |
| 3-tier cache (fakeredis) | Tier 1 exact-match, Tier 2 semantic, Tier 3 embedding; invalidation on document change |
| Admin dashboard | Cost breakdown per tier, cache hit rates, query audit log, health status — built with ui-ux-pro-max |
| Chat UI polish | Streaming output, expandable source panel, cache tier badge, confidence badge, New Conversation — built with ui-ux-pro-max |
| Document manager | Sortable/filterable table, delete with cascade + cache invalidation, storage indicator — built with ui-ux-pro-max |
| Audit logging | `query_log`, `token_usage`, `ingestion_log` tables written on every operation |
| Basic security | File type/size allowlist validation, API key never logged, query input sanitization |

### Out of Scope (Deferred Post-MVP)

| Item | Reason |
|------|--------|
| Authentication / RBAC | Local POC — single user |
| OpenTelemetry distributed tracing | Overkill for local demo |
| Prometheus metrics endpoint | Admin dashboard covers observability needs |
| CI/CD pipeline | Not needed for local prototype |
| Production storage migration (Qdrant, PostgreSQL, Redis Cluster) | fakeredis + SQLite + ChromaDB sufficient |
| Hybrid search (BM25 + RRF + cross-encoder reranker) | Dense-only retrieval sufficient for POC |
| Phase 5 enhancements (agentic RAG, multi-collection, feedback loop, OCR, ZIP upload) | Post-MVP |

---

## 3. Architecture

### New Modules (8 new files + extensions)

```
core/
  llm_service.py             OpenRouter client; streaming; retry+backoff; token capture; fallback chain
  complexity_classifier.py   Rule-based query complexity → Tier enum (SIMPLE/MODERATE/COMPLEX)
  retriever.py               Dense vector search; similarity threshold; context assembly; source metadata
                             Also owns RetrievedChunk dataclass (shared via core/schemas.py import)
  prompt_builder.py          System prompt; numbered source context; conversation history; user query
  confidence.py              Similarity scores + chunk count → Low/Medium/High confidence label
  schemas.py                 NEW: shared dataclasses — RetrievedChunk, QueryResult, CacheEntry
  cache/
    cache_manager.py         Orchestrates Tier 1 → Tier 2 → Tier 3; invalidation; metrics counters
                             Owns all cache read/write including Tier 3 embedding lookups
    redis_client.py          fakeredis wrapper; exposes get/set/delete/scan; swappable for real Redis

ingestion/parsers/
  pptx_parser.py             python-pptx: slides → text + metadata
  html_parser.py             BeautifulSoup4: HTML → clean text + metadata
  json_xml_parser.py         json/lxml: structured data → flattened text chunks

models/db.py                 EXTEND existing Phase 1 schema (Document, Chunk, Collection, Conversation,
                             Config) — add QueryLog, TokenUsage, IngestionLog tables via new Alembic migration

app/pages/
  admin.py                   NEW Page 3: admin dashboard (ui-ux-pro-max, dark bento-grid)
  chat.py                    REWRITE: wire full RAG chain, streaming, all badges (ui-ux-pro-max)
  documents.py               EXTEND: sortable table, delete cascade, storage indicator (ui-ux-pro-max)
```

### Shared Dataclasses (`core/schemas.py`)

```python
@dataclass
class RetrievedChunk:
    text: str
    doc_name: str
    page_number: int | None
    chunk_index: int
    score: float          # cosine similarity, 0–1

@dataclass
class QueryResult:
    answer: str
    sources: list[RetrievedChunk]
    model_used: str
    model_tier: str       # "SIMPLE" | "MODERATE" | "COMPLEX"
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    cache_tier_hit: str | None   # "TIER_1" | "TIER_2" | None
    confidence: str       # "LOW" | "MEDIUM" | "HIGH"
    fallback_tier: str | None
```

### Session Identity

Each browser session generates a UUID stored in `st.session_state["session_id"]` on first load. This UUID is written to `QueryLog.session_id` for every query in that session.

### Conversation Persistence (SQLite)

Conversations are persisted to the existing `conversations` table in SQLite (already defined in Phase 1 `models/db.py`) using SQLAlchemy ORM backed by Python's `sqlite3` engine. This means conversation history survives app restarts.

**Behaviour:**
- On session start: load the most recent conversation from `conversations` where `session_id` matches (if any) into `st.session_state["messages"]`
- After each assistant response: upsert the full `messages_json` list to the `conversations` table row for this `session_id`
- "New Conversation" button: insert a fresh row with a new `session_id`, clear `st.session_state["messages"]`
- Conversation history passed to `prompt_builder` is always read from `st.session_state["messages"]` (in-memory for performance); SQLite is the durable backup

**Schema (existing, no migration needed):**
```python
class Conversation(Base):
    __tablename__ = "conversations"
    id            = Column(Integer, primary_key=True)
    user_id       = Column(String, default="local")   # single-user POC
    session_id    = Column(String, index=True)         # UUID from st.session_state
    messages_json = Column(Text)                       # JSON list of {role, content, timestamp}
    created_at    = Column(DateTime, default=func.now())
    updated_at    = Column(DateTime, onupdate=func.now())
```

### Configuration

All configurable values live in `config/settings.py` (existing Pydantic `BaseSettings`). New keys to add:

```
# OpenRouter
OPENROUTER_API_KEY          (env var, never logged)
OPENROUTER_BASE_URL         = "https://openrouter.ai/api/v1"
OPENROUTER_HTTP_REFERER     = "https://intelrag.local"
OPENROUTER_X_TITLE          = "IntelRAG"

# Model tiers
TIER_1_MODEL  = "meta-llama/llama-3.1-8b-instruct:free"
TIER_2_MODEL  = "google/gemini-2.0-flash"
TIER_3_MODEL  = "openai/gpt-4o-mini"

# LLM timeouts / retry
LLM_TIMEOUT_SECONDS     = 60
LLM_MAX_RETRIES         = 3
LLM_RETRY_BASE_DELAY    = 1.0   # seconds; delay = base * 2^attempt + uniform_jitter(0, 0.5)

# Cache TTLs
CACHE_EXACT_TTL             = 86400    # 24h in seconds
CACHE_SEMANTIC_TTL          = 172800   # 48h in seconds
CACHE_SEMANTIC_THRESHOLD    = 0.95     # cosine similarity

# Retrieval
TOP_K_RETRIEVAL         = 20
TOP_K_RERANK            = 5
SIMILARITY_THRESHOLD    = 0.7

# Conversation
CONVERSATION_HISTORY_TURNS = 6
```

---

## 4. Complete Data Flow

```
User Query
    │
    ├─ generate session_id if not exists (st.session_state["session_id"] = uuid4())
    │
    ▼
cache_manager.lookup(query, doc_set_hash, model_id)
  ├─ Tier 1: SHA-256(query + doc_set_hash + model_id) → Redis STRING get
  │     HIT → return QueryResult (cache_tier_hit="TIER_1")
  ├─ Tier 2: embed query → cosine scan all tier2:* entries → best match >= 0.95
  │     HIT → return QueryResult (cache_tier_hit="TIER_2")
  └─ MISS → proceed
    │
    ▼
complexity_classifier.classify(query, turn_count, retrieved_doc_count=1)
  └─ returns: Tier enum + model_id string
    │
    ▼
retriever.retrieve(query)
  ├─ cache_manager.get_embedding(query, model_name)   ← Tier 3 check for QUERY embedding
  │     MISS: compute embedding, then cache_manager.store_embedding(query, embedding)
  ├─ ChromaDB similarity search: top_k=20, cosine distance
  ├─ filter: score < 0.7 dropped
  ├─ deduplicate: same doc_id + adjacent chunk_index merged
  ├─ order by score descending, take top_k_rerank=5
  └─ returns: list[RetrievedChunk]
    │
    ├─ re-classify with retrieved_doc_count=len(chunks) — FOR BADGE/LOGGING ONLY
    │    (the model_id selected in the first classification is used for the LLM call;
    │     the second classification updates the complexity badge displayed to the user
    │     and the model_tier written to query_log — it does NOT change the model used)
    │
    ▼
prompt_builder.build(query, chunks, conversation_history)
  └─ returns: list[ChatMessage] (system + context + history + user)
    │
    ▼
llm_service.generate(messages, model_id, stream=True)
  ├─ call OpenRouter, stream tokens to UI via generator
  ├─ on HTTP 5xx / connection timeout / empty choices → fallback chain
  │     SIMPLE fails → retry with TIER_2_MODEL
  │     MODERATE fails → retry with TIER_3_MODEL
  │     COMPLEX fails → raise with last error + serve cache if available
  ├─ capture tokens_in, tokens_out, cost_usd from response usage
  └─ returns: answer_text, tokens_in, tokens_out, cost_usd, fallback_tier
    │
    ▼
confidence.score(chunks)
  └─ avg_score = mean([c.score for c in chunks])
     HIGH: avg_score >= 0.80 and len(chunks) >= 3
     MEDIUM: avg_score >= 0.65 or len(chunks) >= 2
     LOW: otherwise
    │
    ▼
cache_manager.store(query, doc_set_hash, model_id, result)
  ├─ Tier 1: set key=SHA-256(query+doc_set_hash+model_id), value=QueryResult JSON, ex=CACHE_EXACT_TTL
  └─ Tier 2: store tier2:{uuid} hash with fields embedding+response; add to tier2:index set; set TTL
    │
    ▼
query_log.write(QueryLog row)   ← see Section 10 for schema
token_usage.upsert(date, tier, tokens, cost)
    │
    ▼
Streamlit UI
  ├─ streamed tokens rendered incrementally
  ├─ cache badge: "⚡ Tier 1 Hit" | "🔮 Tier 2 Hit" | "🆕 Fresh"
  ├─ model badge: "Llama 3.1 Free" | "Gemini Flash" | "GPT-4o-mini"
  ├─ confidence badge: 🟢 High | 🟡 Medium | 🔴 Low
  ├─ complexity indicator on user bubble: pill showing "SIMPLE" | "MODERATE" | "COMPLEX"
  └─ source panel: expandable accordion, one entry per RetrievedChunk
```

---

## 5. Caching Design (fakeredis, 3 tiers)

All tiers use `fakeredis.FakeRedis()` — identical API to real Redis, swappable via one config line.

### Tier 1 — Exact-Match Response Cache

| Aspect | Detail |
|--------|--------|
| Redis structure | `STRING` |
| Key | `cache:exact:{SHA-256(query_text + doc_set_hash + model_id)}` |
| Value | JSON-serialized `QueryResult` |
| TTL | `CACHE_EXACT_TTL` (default 24h = 86400s) |
| Hit criteria | Identical query text + same document corpus hash + same model |

### Tier 2 — Semantic Response Cache

| Aspect | Detail |
|--------|--------|
| Redis structures | `HASH` per entry at `cache:semantic:{uuid4}` with fields `embedding` (bytes) and `response` (JSON); `SET` at `cache:semantic:index` holding all entry keys |
| Lookup | Embed incoming query → iterate `cache:semantic:index` → load each entry's `embedding` → compute cosine similarity → return best match if >= `CACHE_SEMANTIC_THRESHOLD` (0.95) |
| Write | `hset cache:semantic:{uuid} embedding {bytes} response {json}`, `sadd cache:semantic:index {uuid}`, `expire cache:semantic:{uuid} CACHE_SEMANTIC_TTL` |
| TTL | `CACHE_SEMANTIC_TTL` (default 48h = 172800s) — set on the hash key; entry is NOT removed from the index set on TTL expiry (stale key check: if `exists(cache:semantic:{uuid})` returns 0, skip during scan and remove from index) |
| Scale note | Brute-force scan is acceptable for POC (<10K entries). Future upgrade path: RediSearch VSS index. |

### Tier 3 — Embedding Cache

| Aspect | Detail |
|--------|--------|
| Redis structure | `STRING` (binary-safe) |
| Key | `cache:embedding:{SHA-256(text + model_name)}` |
| Value | `numpy` array serialized via `numpy.tobytes()` |
| TTL | No expiry (embeddings are deterministic for a fixed model) |
| Flush trigger | On `EMBEDDING_MODEL` config change: `cache_manager.flush_embedding_cache()` deletes all `cache:embedding:*` keys |
| Ownership | `cache_manager` is the only caller — `retriever.py` calls `cache_manager.get_embedding()` / `cache_manager.store_embedding()`. `retriever.py` never touches Redis directly. |

### doc_set_hash (Cache Corpus Fingerprint)

```
doc_set_hash = SHA-256(
    "|".join(sorted([
        f"{doc.id}:{doc.ingestion_timestamp.isoformat()}"
        for doc in all_active_documents()
    ]))
)
```

Recomputed after every document add, update, or delete. Stored in memory (`st.session_state["doc_set_hash"]`) and refreshed at the start of each query. Used as part of Tier 1 cache keys so that adding or removing any document automatically invalidates all existing exact-match entries.

### Cache Invalidation on Document Change

1. Recompute `doc_set_hash` (new value means all Tier 1 keys with old hash are stale — they expire naturally via TTL, or optionally: `delete cache:exact:*` for immediate flush)
2. Flush all Tier 2 entries: `smembers cache:semantic:index` → delete each `cache:semantic:{uuid}` → `delete cache:semantic:index`
3. **Tier 3 is NOT flushed** — chunk embeddings are reusable regardless of document set changes

---

## 6. Complexity Classifier

**File**: `core/complexity_classifier.py`

Rule-based, ~5ms, no ML model:

```python
COMPLEX_KEYWORDS  = {"compare", "contrast", "synthesize", "recommend",
                     "evaluate", "contradict", "analyze", "assess", "critique"}
MODERATE_KEYWORDS = {"summarize", "explain", "describe", "outline", "overview"}
SIMPLE_KEYWORDS   = {"define", "what is", "who is", "when", "list", "name", "how many"}

def classify(query: str, turn_count: int, retrieved_doc_count: int = 1) -> tuple[Tier, str]:
    tokens = query.lower().split()
    token_set = set(tokens)

    # Hard-signal overrides (order matters: Complex > Moderate > Simple)
    if token_set & COMPLEX_KEYWORDS:
        return Tier.COMPLEX, settings.TIER_3_MODEL
    if token_set & MODERATE_KEYWORDS:
        return Tier.MODERATE, settings.TIER_2_MODEL
    if token_set & SIMPLE_KEYWORDS and len(tokens) < 20:
        return Tier.SIMPLE, settings.TIER_1_MODEL

    # Depth / breadth escalation
    if turn_count >= 5 or retrieved_doc_count >= 4:
        return Tier.COMPLEX, settings.TIER_3_MODEL
    if turn_count >= 3 or retrieved_doc_count >= 2:
        return Tier.MODERATE, settings.TIER_2_MODEL

    # Length fallback
    if len(tokens) < 15:
        return Tier.SIMPLE, settings.TIER_1_MODEL
    if len(tokens) < 40:
        return Tier.MODERATE, settings.TIER_2_MODEL
    return Tier.COMPLEX, settings.TIER_3_MODEL
```

### Fallback Chain (LLM Failure)

Failure is defined as any of: HTTP 5xx response, connection timeout (`LLM_TIMEOUT_SECONDS` exceeded), or `response.choices` is empty/None. **Does not trigger on 4xx** (bad request = caller's fault, not a model availability issue).

```
SIMPLE fails  (above conditions) → retry with TIER_2_MODEL, log fallback_tier="MODERATE"
MODERATE fails                   → retry with TIER_3_MODEL, log fallback_tier="COMPLEX"
COMPLEX fails                    → raise LLMUnavailableError (class defined in core/llm_service.py); serve from cache if available; show error toast
```

The `llm_service` internal retry (exponential backoff, Section 7) fires first within one tier. The fallback chain escalates to the next tier only after all retries for the current tier are exhausted.

---

## 7. LLM Service

**File**: `core/llm_service.py`

```python
client = openai.AsyncOpenAI(
    base_url=settings.OPENROUTER_BASE_URL,
    api_key=settings.OPENROUTER_API_KEY,   # loaded from env, never logged
    default_headers={
        "HTTP-Referer": settings.OPENROUTER_HTTP_REFERER,
        "X-Title": settings.OPENROUTER_X_TITLE,
    }
)
```

Retry logic (within a single tier, before fallback):
```
attempt 0: immediate
attempt 1: delay = 1.0 * 2^1 + uniform(0, 0.5)  = ~2.0–2.5s
attempt 2: delay = 1.0 * 2^2 + uniform(0, 0.5)  = ~4.0–4.5s
max attempts: LLM_MAX_RETRIES = 3
```

Streaming: yield tokens via `async for chunk in response` — caller (`chat.py`) writes each token to `st.empty()` placeholder, building the full response incrementally.

Token cost estimation:
```python
MODEL_PRICES = {
    "meta-llama/llama-3.1-8b-instruct:free": 0.0,
    "google/gemini-2.0-flash": 0.10 / 1_000_000,
    "openai/gpt-4o-mini": 0.15 / 1_000_000,
}
cost_usd = (tokens_in + tokens_out) * MODEL_PRICES[model_id]
```

---

## 8. RAG Retrieval

**File**: `core/retriever.py`

```
def retrieve(query: str) -> list[RetrievedChunk]:
    1. embedding = cache_manager.get_embedding(query, settings.EMBEDDING_MODEL)
       if None: embedding = embedding_service.embed(query)
                cache_manager.store_embedding(query, embedding)

    2. results = vector_store.query(embedding, n_results=TOP_K_RETRIEVAL)
       # returns list of (chunk_text, metadata, score)

    3. filtered = [r for r in results if r.score >= SIMILARITY_THRESHOLD]

    4. deduplicated = remove_adjacent_overlaps(filtered)
       # merge chunks with same doc_id and chunk_index differing by 1

    5. ordered = sorted(deduplicated, key=lambda r: r.score, reverse=True)

    6. final = ordered[:TOP_K_RERANK]

    7. return [RetrievedChunk(text, doc_name, page_number, chunk_index, score)
               for each final result]
```

---

## 9. Prompt Builder

**File**: `core/prompt_builder.py`

Conversation history = last `CONVERSATION_HISTORY_TURNS` (default 6) turns from `st.session_state["messages"]`.

**Sprint 2 note**: In Sprint 2, `prompt_builder` is built with an empty conversation history (single-turn). Sprint 5 extends it to pass the actual history — no rewrite needed, just changing the default empty-list argument to the actual session history.

System prompt enforces:
- Cite sources as `[Source N]` inline; list full references at end of response
- If context is insufficient: respond "I don't have enough information in the indexed documents to answer this." — never invent facts
- Professional, concise tone

---

## 10. New DB Tables (Audit & Analytics)

Added to `models/db.py` via a new Alembic migration (does not touch existing Phase 1 tables: `documents`, `chunks`, `collections`, `conversations`, `config`).

```python
class QueryLog(Base):
    __tablename__ = "query_log"
    id              = Column(Integer, primary_key=True)
    timestamp       = Column(DateTime, default=func.now(), index=True)
    session_id      = Column(String)   # UUID from st.session_state["session_id"]
    query_text      = Column(Text)
    model_used      = Column(String)   # full OpenRouter model ID
    model_tier      = Column(String)   # "SIMPLE" | "MODERATE" | "COMPLEX"
    tokens_in       = Column(Integer)
    tokens_out      = Column(Integer)
    cost_usd        = Column(Float)
    latency_ms      = Column(Integer)
    cache_tier_hit  = Column(String, nullable=True)   # "TIER_1" | "TIER_2" | None
    confidence      = Column(String)   # "LOW" | "MEDIUM" | "HIGH"
    fallback_tier   = Column(String, nullable=True)   # tier used if fallback triggered
    chunks_retrieved = Column(Integer)

class TokenUsage(Base):
    __tablename__ = "token_usage"
    id           = Column(Integer, primary_key=True)
    date         = Column(Date, index=True)           # one row per calendar day
    tier_1_tokens = Column(Integer, default=0)
    tier_2_tokens = Column(Integer, default=0)
    tier_3_tokens = Column(Integer, default=0)
    tier_1_cost  = Column(Float, default=0.0)
    tier_2_cost  = Column(Float, default=0.0)
    tier_3_cost  = Column(Float, default=0.0)
    total_cost   = Column(Float, default=0.0)

class IngestionLog(Base):
    __tablename__ = "ingestion_log"
    id             = Column(Integer, primary_key=True)
    document_id    = Column(Integer, ForeignKey("documents.id"))
    timestamp      = Column(DateTime, default=func.now())
    status         = Column(String)   # "success" | "failed" | "duplicate"
    chunks_created = Column(Integer)
    duration_ms    = Column(Integer)
    error_message  = Column(Text, nullable=True)
```

**TokenUsage write pattern**: After each query completes, upsert the daily summary row:
```sql
INSERT INTO token_usage (date, tier_X_tokens, tier_X_cost, total_cost)
VALUES (today, N, $X, $total)
ON CONFLICT (date) DO UPDATE SET
  tier_X_tokens = tier_X_tokens + N,
  tier_X_cost   = tier_X_cost + $X,
  total_cost    = total_cost + $total
```

Requires a `UNIQUE` constraint on `date` column.

**Sprint sequencing**: `QueryLog` and `IngestionLog` tables are created in Sprint 6, but Sprint 4's `cache_manager` and Sprint 2's `llm_service` call a write function that is a **no-op stub** until Sprint 6. The stub has the correct signature so no refactor is needed in Sprint 6 — just swap the stub for the real DB write.

---

## 11. Health Check

**New method**: `core/health.py` — called by admin dashboard Row 4.

```python
def check_all() -> dict[str, bool]:
    return {
        "vector_store": _ping_chromadb(),       # try list_collections()
        "metadata_db":  _ping_sqlite(),          # try SELECT 1
        "cache":        _ping_fakeredis(),        # try redis.ping()
        "openrouter":   _ping_openrouter(),       # HEAD request to base URL, timeout=3s
    }
```

---

## 12. Admin Dashboard Layout (ui-ux-pro-max)

**File**: `app/pages/admin.py`
**Style**: dark mode, bento-grid, professional SaaS aesthetic (via ui-ux-pro-max skill at implementation time).

```
ROW 1 — KPI Cards (4 equal columns)
  [Total Queries Today]  [Cache Hit Rate %]  [Cost Saved via Cache]  [Docs Indexed]

ROW 2 — Split panels (50/50)
  LEFT: Cost Breakdown per Tier              RIGHT: Cache Performance
    Tier 1 (Free):    $0.00 | N queries        Tier 1 Exact:    XX% hit rate
    Tier 2 (Gemini):  $X.XX | N queries        Tier 2 Semantic: XX% hit rate
    Tier 3 (OpenAI):  $X.XX | N queries        Tier 3 Embed:    XX% hit rate
    ─────────────────────────                  Avg cached latency:   Xms
    Total:            $X.XX                    Avg fresh latency:    Xms

ROW 3 — Query Audit Log (full-width, searchable by query text or session)
  Columns: Timestamp | Query | Model | Tier | Tokens | Cost | Cache | Confidence | Latency

ROW 4 — Health Status Bar (one colored dot per service)
  ● Vector Store (ChromaDB)  ● Metadata DB (SQLite)  ● Cache (fakeredis)  ● OpenRouter API
```

---

## 13. Chat UI Enhancements (ui-ux-pro-max)

**File**: `app/pages/chat.py` — full rewrite.
**Style**: clean modern chat aesthetic via ui-ux-pro-max.

| Element | Detail |
|---------|--------|
| Streaming | Tokens render incrementally via `st.empty()` placeholder updated in loop |
| Cache badge | Pill above assistant bubble — "⚡ Tier 1 Hit" (green) / "🔮 Tier 2 Hit" (purple) / "🆕 Fresh" (grey) |
| Confidence badge | Color-coded pill — 🟢 High / 🟡 Medium / 🔴 Low |
| Model badge | Small tag — "Llama 3.1 Free" / "Gemini Flash" / "GPT-4o-mini" |
| Complexity indicator | Pill on user message bubble (appended after response received) — "SIMPLE" / "MODERATE" / "COMPLEX" |
| Source panel | Expandable `st.expander` below each response — one row per RetrievedChunk with doc name, page, excerpt, similarity score |
| New Conversation | Button clears `st.session_state["messages"]` and generates new `session_id` |

---

## 14. Document Manager Enhancements (ui-ux-pro-max)

**File**: `app/pages/documents.py` — extension.

- **Storage indicator** (top of page): total docs / total chunks / estimated ChromaDB size
- **Document table**: `st.dataframe` with sort + filter by type/status; columns: Name, Type, Size, Pages, Chunks, Upload Date, Status
- **Status badges**: Indexed (green) / Processing (yellow) / Failed (red)
- **Delete action**: confirmation dialog → cascade: (1) delete from file store, (2) delete chunks from vector store, (3) delete from metadata DB, (4) cache invalidation per Section 5 policy (Tier 1 + Tier 2 flush; Tier 3 untouched)

---

## 15. Build Sequence (Sprint Order)

| Sprint | Modules Built | Milestone / Test |
|--------|--------------|-----------------|
| **S1** | Phase 1 gaps: `vector_store.py` abstraction interface, PPTX/HTML/JSON-XML parsers, metadata extraction, missing tests (T-1.2.6, T-1.2.8, T-1.3.6–T-1.3.14, T-1.5.4–T-1.5.5, T-1.6.7) | All 47 Phase 1 tasks complete; upload PPTX, HTML, JSON files successfully |
| **S2** | `core/schemas.py`, `core/llm_service.py`, `core/retriever.py`, `core/prompt_builder.py` (single-turn), wire into `chat.py` with single fixed model | Ask a question → get cited answer with source panel; no routing/cache yet |
| **S3** | `core/complexity_classifier.py`, model tier routing + fallback chain in `llm_service.py` | Ask simple/complex questions → see different model badges; fallback logged on simulated failure |
| **S4** | `core/cache/redis_client.py` (fakeredis), `core/cache/cache_manager.py` (all 3 tiers), `doc_set_hash`, cache invalidation; query_log/token_usage write stubs added | Ask same question twice → Tier 1 badge; ask similar question → Tier 2 badge; delete doc → cache clears |
| **S5** | Multi-turn conversation history in `prompt_builder.py`; SQLite conversation persistence (load on session start, upsert after each response, New Conversation clears + creates new row); `core/confidence.py`; confidence badge in `chat.py` | Follow-up questions maintain context; history survives app restart; confidence badge appears on all responses |
| **S6** | Alembic migration for audit tables, real `query_log.write`, `ingestion_log.write`, `token_usage.upsert` | Every query logged; ingestion audit trail populated |
| **S7** | `core/health.py`, `app/pages/admin.py`, full chat/doc UI polish (ui-ux-pro-max invoked here) | Full demo-ready MVP — all Done Criteria below pass |

---

## 16. Done Criteria (MVP)

All the following work on a local machine with only `pip install -e ".[dev]"` + `streamlit run app/main.py`:

1. Upload a PDF, DOCX, and CSV → all three indexed with per-file progress badges (Queued → Processing → Indexed)
2. Upload an HTML and PPTX file → both indexed and queryable
3. Ask a simple factual question → "SIMPLE" complexity indicator + free Llama model badge + "🆕 Fresh" cache badge + cited answer with source panel + confidence badge rendered
4. Ask the same question again → "⚡ Tier 1 Cache Hit" badge, response in < 200ms
5. Ask a semantically similar rephrase of the same question → "🔮 Tier 2 Semantic Hit" badge
6. Ask a complex multi-document analysis question → "COMPLEX" indicator + GPT-4o-mini badge + confidence badge
7. Ask a follow-up question → assistant references prior context from conversation history; restart the app and resume the same conversation → history reloads from SQLite
8. Open Admin dashboard → see per-tier cost breakdown, cache hit rates per tier, full query audit log (all 9 queries visible), health status all green
9. Delete a document → cache invalidated **synchronously** (before the delete operation returns to the UI); subsequent queries referencing that doc no longer return it; audit log shows the deleted doc is absent from retrieved sources

---

*Spec v2 — 2026-03-26. Post-review fixes: Tier 2 Redis structure defined, doc_set_hash defined, sprint sequencing fixed, Tier 3 ownership clarified, failure conditions defined, backoff formula added, TokenUsage upsert pattern specified, cross-section invalidation references aligned, session_id sourcing defined, shared dataclasses added, health check module added.*
