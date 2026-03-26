# IntelRAG — Task List

> Derived from [PRD.md](./PRD.md) v1.0 | Created: 2026-03-15
> Priority: **P0** = Must-have (launch blocker) | **P1** = Should-have | **P2** = Nice-to-have

### Progress (updated in real-time)

| Phase | Done | Total | Status |
|-------|------|-------|--------|
| **Phase 1** — Foundation | 44 | 47 | In progress |
| Phase 2 — Core RAG | 0 | 42 | Pending |
| Phase 3 — Enterprise Caching | 0 | 27 | Pending |
| Phase 4 — Polish & Production | 0 | 45 | Pending |
| Phase 5 — Enhancements | 0 | 27 | Pending |

---

## Phase 1: Foundation (Weeks 1–3)

### 1.1 Project Scaffolding & Infrastructure

- [x] **T-1.1.1** Create project directory structure per PRD Section 8
  ```
  intelrag/
  ├── app/                  # Streamlit pages
  ├── core/                 # RAG engine, cache manager, LLM service
  ├── ingestion/            # Parsers, chunking, embedding pipeline
  ├── models/               # SQLAlchemy/SQLModel ORM models
  ├── config/               # Settings, environment profiles
  ├── utils/                # Shared helpers
  ├── tests/                # pytest test suite
  ├── data/                 # Local dev storage (uploads, chroma, sqlite)
  ├── docker/               # Dockerfiles, compose configs
  ├── .env.example
  ├── pyproject.toml
  └── README.md
  ```
- [x] **T-1.1.2** Initialize `pyproject.toml` with `poetry` or `uv`; pin Python 3.11+ — **P0**
- [x] **T-1.1.3** Add core dependencies: `streamlit`, `langchain` / `llama-index`, `chromadb`, `sentence-transformers`, `openai`, `redis`, `sqlalchemy`, `pydantic-settings`, `structlog` — **P0**
- [x] **T-1.1.4** Add dev dependencies: `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy`, `fakeredis` — **P0**
- [x] **T-1.1.5** Create `Dockerfile` for the application — **P0**
- [x] **T-1.1.6** Create `docker-compose.yml` with services: `app`, `redis`, `qdrant`, `postgres` (dev profile uses SQLite + ChromaDB instead) — **P0**
- [x] **T-1.1.7** Create `.env.example` with all required env vars (`OPENROUTER_API_KEY`, `DB_USER`, `DB_PASSWORD`, `REDIS_URL`, etc.) — **P0**
- [x] **T-1.1.8** Set up `pydantic-settings` config module with `development` / `staging` / `production` profiles — **P0** `[FR-5.5]`
- [x] **T-1.1.9** Set up `structlog` JSON logging with correlation IDs — **P0** `[FR-5.3]`
- [x] **T-1.1.10** Configure `ruff` and `mypy` with strict settings; add `pre-commit` hooks — **P1**
- [x] **T-1.1.11** Set up `pytest` with `conftest.py`, fixtures for DB, Redis (fakeredis), vector store — **P1**

### 1.2 Storage Layer Setup

- [x] **T-1.2.1** Create local file store module (`core/storage/file_store.py`) — write-once storage for raw uploads at `./data/uploads/{doc_id}/{filename}` — **P0** `[Storage Layer 1]`
- [x] **T-1.2.2** Define SQLAlchemy/SQLModel ORM models for metadata DB — **P0** `[Storage Layer 3]`
  - [x] `documents` table (id, filename, file_type, file_size, content_hash, file_store_path, status, chunk_count, page_count, created_at)
  - [x] `chunks` table (id, document_id, chunk_index, page_number, char_offset, vector_store_id, text_preview)
  - [x] `collections` table (id, name, description, document_ids, created_by)
  - [x] `conversations` table (id, user_id, messages_json, created_at, updated_at)
  - [x] `config` table (key, value, updated_at, updated_by)
- [x] **T-1.2.3** Set up Alembic for database migrations — **P0**
- [x] **T-1.2.4** Create SQLite dev database initialization script — **P0**
- [x] **T-1.2.5** Initialize ChromaDB vector store module (`core/storage/vector_store.py`) with HNSW index, cosine similarity — **P0** `[Storage Layer 2]`
- [ ] **T-1.2.6** Create vector store abstraction layer (interface) so ChromaDB can be swapped for Qdrant via config — **P1**
- [x] **T-1.2.7** Write tests for file store (upload, retrieve, delete) — **P1**
- [ ] **T-1.2.8** Write tests for metadata DB CRUD operations — **P1**

### 1.3 Document Parsers

- [x] **T-1.3.1** Create parser factory (`ingestion/parsers/factory.py`) — auto-detect file type via `python-magic` / `mimetypes` and route to correct parser — **P0** `[FR-1.4]`
- [x] **T-1.3.2** Implement PDF parser using `PyMuPDF` (fitz) — extract text, page numbers, metadata — **P0** `[FR-1.2]`
- [x] **T-1.3.3** Implement DOCX parser using `python-docx` — **P0** `[FR-1.2]`
- [x] **T-1.3.4** Implement TXT / Markdown parser — **P0** `[FR-1.2]`
- [x] **T-1.3.5** Implement CSV / XLSX parser using `pandas` + `openpyxl` — **P0** `[FR-1.2]`
- [ ] **T-1.3.6** Implement PPTX parser using `python-pptx` — **P1** `[FR-1.2]`
- [ ] **T-1.3.7** Implement HTML parser using `BeautifulSoup4` — **P1** `[FR-1.2]`
- [ ] **T-1.3.8** Implement JSON / XML parser using `json` / `lxml` — **P1** `[FR-1.2]`
- [ ] **T-1.3.9** Implement EPUB parser using `ebooklib` — **P2** `[FR-1.2]`
- [ ] **T-1.3.10** Implement OCR parser for images using `pytesseract` + `Pillow` — **P2** `[FR-1.2]`
- [ ] **T-1.3.11** Implement source code parser (plain text with language detection) — **P2** `[FR-1.2]`
- [ ] **T-1.3.12** Implement RTF / DOC parser — **P2** `[FR-1.2]`
- [ ] **T-1.3.13** Document metadata extraction for all parsers (title, author, page count, creation date, file size) — **P1** `[FR-1.5]`
- [ ] **T-1.3.14** Write unit tests for each parser with sample files — **P1**

### 1.4 Chunking Pipeline

- [x] **T-1.4.1** Create chunking module (`ingestion/chunker.py`) with configurable strategy — **P0** `[PRD Section 10]`
- [x] **T-1.4.2** Implement recursive character splitting (default: 1000 chars, 200 overlap) — **P0**
- [ ] **T-1.4.3** Implement sentence-boundary-aware semantic chunking — **P1**
- [ ] **T-1.4.4** Implement table-aware chunking (preserve table structures) — **P2**
- [ ] **T-1.4.5** Implement code-aware chunking (respect function/class boundaries) — **P2**
- [x] **T-1.4.6** Add configurable parameters: `chunk_size`, `chunk_overlap`, `chunking_strategy`, `respect_boundaries`, `max_chunks_per_doc` — **P0**
- [x] **T-1.4.7** Write tests for chunking with various document types — **P1**

### 1.5 Embedding Pipeline

- [x] **T-1.5.1** Create embedding service module (`core/embedding_service.py`) — **P0**
- [x] **T-1.5.2** Integrate local `sentence-transformers` model (`all-MiniLM-L6-v2`) as default embedding model — **P0**
- [x] **T-1.5.3** Implement batch embedding (process chunks in batches of 64–128) — **P0**
- [ ] **T-1.5.4** Add abstraction to swap local embeddings for API-based embeddings via config — **P1**
- [ ] **T-1.5.5** Write tests for embedding generation and batch processing — **P1**

### 1.6 Document Ingestion Pipeline (End-to-End)

- [x] **T-1.6.1** Create ingestion orchestrator (`ingestion/pipeline.py`) — ties together: file store → parser → chunker → embedder → vector store → metadata DB — **P0** `[PRD Section 10]`
- [x] **T-1.6.2** Implement SHA-256 duplicate detection based on file content hash — **P1** `[FR-1.8]`
- [x] **T-1.6.3** Implement text cleaning & normalization (whitespace, encoding, header/footer removal) — **P1**
- [x] **T-1.6.4** Store chunk metadata in vector store payload: `doc_id`, `chunk_index`, `page_number`, `source_file`, `char_offset`, `timestamp` — **P0**
- [x] **T-1.6.5** Update metadata DB on ingestion completion (document status, chunk count) — **P0**
- [x] **T-1.6.6** Handle ingestion errors gracefully — mark document as `failed`, log error, continue with next document — **P0**
- [ ] **T-1.6.7** Write integration tests for full ingestion pipeline (upload → query readiness) — **P1**

### 1.7 Basic Streamlit UI

- [x] **T-1.7.1** Create multi-page Streamlit app skeleton with sidebar navigation — **P0**
- [x] **T-1.7.2** Set up `st.set_page_config(layout="wide")` and custom CSS for professional styling — **P0**
- [x] **T-1.7.3** Build Document Upload page — `st.file_uploader` with `accept_multiple_files=True` — **P0** `[FR-1.1]`
- [x] **T-1.7.4** Implement per-file upload progress display with status badges (queued / processing / indexed / failed) — **P0** `[FR-1.3]`
- [x] **T-1.7.5** Implement file size validation (200 MB limit, configurable) — **P0** `[FR-1.9]`
- [x] **T-1.7.6** Build basic Chat page — `st.chat_input` + `st.chat_message` for simple single-turn Q&A — **P0** `[FR-2.1]`
- [x] **T-1.7.7** Wire upload page → ingestion pipeline (trigger processing on upload) — **P0**
- [x] **T-1.7.8** Wire chat page → simple vector search + placeholder LLM response — **P0**

---

## Phase 2: Core RAG (Weeks 4–6)

### 2.1 OpenRouter Integration

- [ ] **T-2.1.1** Create LLM service module (`core/llm_service.py`) with OpenRouter client using `openai` SDK — **P0** `[FR-4.1]`
- [ ] **T-2.1.2** Configure `base_url`, API key, HTTP-Referer, X-Title headers — **P0**
- [ ] **T-2.1.3** Implement basic LLM call (non-streaming) with timeout and error handling — **P0**
- [ ] **T-2.1.4** Implement streaming response support (token-by-token) — **P1** `[FR-4.11]`
- [ ] **T-2.1.5** Add retry with exponential backoff for transient errors (429, 503) — **P1**
- [ ] **T-2.1.6** Capture token usage from API response headers (prompt tokens, completion tokens) — **P0** `[FR-4.9]`
- [ ] **T-2.1.7** Write tests for OpenRouter client (mock API responses) — **P1**

### 2.2 Query Complexity Classifier

- [ ] **T-2.2.1** Create classifier module (`core/complexity_classifier.py`) — **P0** `[FR-4.2, FR-4.12]`
- [ ] **T-2.2.2** Implement rule-based classification layer (~5ms target) — **P0**
  - [ ] Query length heuristic (< 15 tokens → Simple)
  - [ ] Question-type keywords ("what is", "who", "when" → Simple; "compare", "analyze" → Complex)
  - [ ] Action keywords ("summarize", "list" → Moderate; "recommend", "evaluate" → Complex)
  - [ ] Conversation depth signals (3+ turns → escalate)
- [ ] **T-2.2.3** Implement model tier mapping: Simple → Free, Moderate → Gemini, Complex → OpenAI — **P0** `[FR-4.3, FR-4.4, FR-4.5]`
- [ ] **T-2.2.4** Add admin override: force specific tier or set max tier ceiling — **P1**
- [ ] **T-2.2.5** Implement optional embedding-based refinement layer (~50ms) — **P2**
- [ ] **T-2.2.6** Write tests for classifier with sample queries across all complexity levels — **P0**

### 2.3 Model Tier Routing

- [ ] **T-2.3.1** Configure Tier 1 (Free) models in settings: `meta-llama/llama-3.1-8b-instruct:free`, `mistralai/mistral-7b-instruct:free`, `google/gemma-2-9b-it:free` — **P0**
- [ ] **T-2.3.2** Configure Tier 2 (Gemini) models in settings: `google/gemini-2.0-flash`, `google/gemini-2.0-pro` — **P0**
- [ ] **T-2.3.3** Configure Tier 3 (OpenAI) models in settings: `openai/gpt-4o`, `openai/gpt-4o-mini` — **P0**
- [ ] **T-2.3.4** Implement model fallback chain: Free → Gemini → OpenAI on failure — **P1** `[FR-4.6]`
- [ ] **T-2.3.5** Implement admin-configurable default model per tier — **P1** `[FR-4.8]`
- [ ] **T-2.3.6** Log model tier used, fallback events, and per-tier token consumption — **P0**
- [ ] **T-2.3.7** Write integration tests for tier routing + fallback — **P1**

### 2.4 RAG Pipeline — Retrieval

- [ ] **T-2.4.1** Create retriever module (`core/retriever.py`) — **P0** `[PRD Section 11]`
- [ ] **T-2.4.2** Implement dense retrieval: embed query → cosine similarity search in vector store → Top-K=20 — **P0**
- [ ] **T-2.4.3** Implement minimum similarity threshold filter (default: 0.7) — **P0**
- [ ] **T-2.4.4** Implement sparse retrieval (BM25 keyword matching) — **P1**
- [ ] **T-2.4.5** Implement Reciprocal Rank Fusion (RRF) to merge dense + sparse results — **P1**
- [ ] **T-2.4.6** Implement cross-encoder re-ranking (`cross-encoder/ms-marco-MiniLM-L-6-v2`) to narrow to Top-K=5 — **P1**
- [ ] **T-2.4.7** Implement context assembly: deduplicate overlapping chunks, order by relevance, trim to model context window — **P0**
- [ ] **T-2.4.8** Attach source metadata to each retrieved chunk (doc name, page number, chunk index) — **P0**
- [ ] **T-2.4.9** Make retrieval parameters configurable (`top_k_retrieval`, `top_k_rerank`, `similarity_threshold`, `hybrid_search`) — **P0**
- [ ] **T-2.4.10** Write tests for retrieval with known-answer queries — **P1**

### 2.5 RAG Pipeline — Generation

- [ ] **T-2.5.1** Create prompt construction module (`core/prompt_builder.py`) — **P0**
- [ ] **T-2.5.2** Design system prompt with: role definition, citation format, "I don't know" instruction, no-hallucination constraint — **P0** `[FR-2.5]`
- [ ] **T-2.5.3** Build prompt template: system prompt + numbered source context + conversation history + user query — **P0**
- [ ] **T-2.5.4** Integrate classifier → retriever → prompt builder → LLM service into a single RAG chain — **P0**
- [ ] **T-2.5.5** Implement source citation parsing from LLM response (extract referenced source numbers) — **P0** `[FR-2.3]`
- [ ] **T-2.5.6** Validate citations against actually retrieved sources (reject hallucinated citations) — **P1**
- [ ] **T-2.5.7** Wire streaming LLM output to Streamlit chat UI — **P1**
- [ ] **T-2.5.8** Write integration tests for full RAG pipeline (query → cited answer) — **P1**

### 2.6 Multi-Turn Conversation

- [ ] **T-2.6.1** Implement session-scoped conversation memory using Streamlit `session_state` — **P0** `[FR-2.2]`
- [ ] **T-2.6.2** Include conversation history in prompt construction (last N turns, configurable) — **P0**
- [ ] **T-2.6.3** Persist conversation to metadata DB (`conversations` table) — **P1**
- [ ] **T-2.6.4** Add "New Conversation" button to clear session — **P0**
- [ ] **T-2.6.5** Write tests for multi-turn context carryover — **P1**

### 2.7 Confidence Scoring

- [ ] **T-2.7.1** Implement confidence scoring module (`core/confidence.py`) — **P1** `[FR-2.4]`
- [ ] **T-2.7.2** Compute confidence based on: retrieval similarity scores, number of relevant chunks found, LLM self-assessment prompt — **P1**
- [ ] **T-2.7.3** Map score to low / medium / high label — **P1**
- [ ] **T-2.7.4** Display color-coded confidence badge on each response in chat UI — **P1**
- [ ] **T-2.7.5** Trigger "I don't know" fallback when confidence is below threshold — **P0** `[FR-2.5]`

---

## Phase 3: Enterprise Caching (Weeks 7–9)

### 3.1 Redis Setup

- [ ] **T-3.1.1** Add Redis Stack (`redis/redis-stack`) to `docker-compose.yml` with RediSearch module — **P0**
- [ ] **T-3.1.2** Create Redis client module (`core/cache/redis_client.py`) with connection pooling — **P0**
- [ ] **T-3.1.3** Configure `maxmemory` (4 GB default) and `allkeys-lru` eviction policy — **P0**
- [ ] **T-3.1.4** Implement `fakeredis` fallback for unit tests — **P1**
- [ ] **T-3.1.5** Add Redis health check to application startup — **P1** `[FR-5.4]`

### 3.2 Tier 1 — Exact-Match Response Cache

- [ ] **T-3.2.1** Create cache manager module (`core/cache/cache_manager.py`) — **P0** `[FR-3.3]`
- [ ] **T-3.2.2** Implement cache key generation: SHA-256 of `(query_text + document_set_hash + model_id)` — **P0**
- [ ] **T-3.2.3** Store full response JSON (answer, sources, metadata) with configurable TTL (default: 24h) — **P0**
- [ ] **T-3.2.4** Check exact-match cache before entering RAG pipeline — **P0**
- [ ] **T-3.2.5** Compute and store `document_set_hash` (hash of all doc content hashes) for invalidation — **P0**
- [ ] **T-3.2.6** Write tests for exact-match cache (hit, miss, TTL expiry) — **P1**

### 3.3 Tier 2 — Semantic Response Cache

- [ ] **T-3.3.1** Create RediSearch vector index for semantic cache (`cache:semantic:idx`) — **P0** `[FR-3.1]`
- [ ] **T-3.3.2** On cache miss, compute query embedding and search semantic cache (cosine similarity >= 0.95) — **P0**
- [ ] **T-3.3.3** Store query embedding + response in semantic cache with TTL (default: 48h) — **P0**
- [ ] **T-3.3.4** Make similarity threshold configurable — **P1** `[FR-3.5]`
- [ ] **T-3.3.5** Write tests for semantic cache (near-duplicate queries should hit) — **P1**

### 3.4 Tier 3 — Embedding Cache

- [ ] **T-3.4.1** Implement embedding cache: key = SHA-256 of chunk text, value = embedding vector — **P0** `[FR-3.2]`
- [ ] **T-3.4.2** Check embedding cache before computing embeddings during ingestion — **P0**
- [ ] **T-3.4.3** Set indefinite TTL (embeddings are deterministic for same model) — **P0**
- [ ] **T-3.4.4** Implement full flush on embedding model change — **P1**
- [ ] **T-3.4.5** Write tests for embedding cache — **P1**

### 3.5 Cache Invalidation

- [ ] **T-3.5.1** Invalidate Tier 1 + Tier 2 entries when documents are added, modified, or deleted — **P0** `[FR-3.4]`
- [ ] **T-3.5.2** Recompute `document_set_hash` on any document change — **P0**
- [ ] **T-3.5.3** Implement periodic pruning of low-hit semantic cache entries — **P1**
- [ ] **T-3.5.4** Implement manual cache purge endpoint for admins — **P1** `[FR-3.7]`
- [ ] **T-3.5.5** Write tests for invalidation scenarios (add doc → old cache invalid) — **P1**

### 3.6 Cache Integration into RAG Pipeline

- [ ] **T-3.6.1** Update RAG pipeline to check caches in order: Tier 1 → Tier 2 → full pipeline — **P0**
- [ ] **T-3.6.2** After full pipeline execution, store results in both Tier 1 and Tier 2 — **P0**
- [ ] **T-3.6.3** Add cache tier hit/miss indicator to response metadata — **P0**
- [ ] **T-3.6.4** Log cache events with correlation ID — **P0**
- [ ] **T-3.6.5** Write end-to-end tests for the full cached RAG flow — **P1**

### 3.7 Cache Metrics Dashboard

- [ ] **T-3.7.1** Track cache hit/miss counters per tier in Redis (HyperLogLog / sorted sets) — **P1** `[FR-3.6]`
- [ ] **T-3.7.2** Calculate estimated cost savings (tokens saved × model pricing) — **P1**
- [ ] **T-3.7.3** Add cache metrics section to admin dashboard (hit rate, size, eviction rate, latency per tier) — **P1**
- [ ] **T-3.7.4** Display cache indicator badge on each chat response ("From cache: Tier 1" / "Fresh response") — **P1**

---

## Phase 4: Polish & Production (Weeks 10–12)

### 4.1 Admin Dashboard

- [ ] **T-4.1.1** Build Admin Dashboard page (Page 3) in Streamlit — **P1** `[FR-5.1]`
- [ ] **T-4.1.2** Usage metrics panel: total queries, tokens consumed, estimated cost (today / week / month) — **P1**
- [ ] **T-4.1.3** Per-tier cost breakdown: Tier 1 (Free), Tier 2 (Gemini), Tier 3 (OpenAI) — **P1**
- [ ] **T-4.1.4** Cache performance charts: hit rate per tier (hourly, daily) — **P1**
- [ ] **T-4.1.5** Document stats: total documents, total chunks, storage used per layer — **P1**
- [ ] **T-4.1.6** Query audit log: searchable table with timestamp, user, query, model, tokens, latency, cache status — **P1** `[FR-5.2]`
- [ ] **T-4.1.7** System config panel: model selection per tier, cache TTLs, chunk size, similarity thresholds — **P1**
- [ ] **T-4.1.8** Health status indicators: vector store, Redis, OpenRouter API, PostgreSQL connectivity — **P1** `[FR-5.4]`

### 4.2 Document Manager Enhancements

- [ ] **T-4.2.1** Build sortable, filterable document table (Name, Type, Size, Pages, Chunks, Date, Status) — **P1** `[FR-1.6]`
- [ ] **T-4.2.2** Add delete document action with confirmation dialog + cascade delete (vector store + metadata + cache invalidation) — **P1** `[FR-1.6]`
- [ ] **T-4.2.3** Add re-index action (re-parse and re-embed a document) — **P2**
- [ ] **T-4.2.4** Add download original file action — **P2**
- [ ] **T-4.2.5** Storage indicator: total documents, chunks, vector store size, Redis usage — **P1**
- [ ] **T-4.2.6** ZIP batch upload (auto-extract and process each file) — **P2** `[FR-1.7]`

### 4.3 Chat UI Enhancements

- [ ] **T-4.3.1** Add expandable source panel (sidebar or accordion) showing retrieved sources with highlighted excerpts — **P1**
- [ ] **T-4.3.2** Add model selector dropdown for power users (override auto-routing) — **P2** `[FR-4.7]`
- [ ] **T-4.3.3** Add export conversation as Markdown / PDF — **P2** `[FR-2.8]`
- [ ] **T-4.3.4** Add dark/light theme toggle — **P2**
- [ ] **T-4.3.5** Implement query rewriting / expansion for improved retrieval — **P1** `[FR-2.6]`
- [ ] **T-4.3.6** Add follow-up question suggestions based on context — **P2** `[FR-2.7]`

### 4.4 Audit & Analytics Store

- [ ] **T-4.4.1** Create audit log tables in metadata DB — **P1** `[Storage Layer 5]`
  - [ ] `query_log` (id, timestamp, user_id, query_text, model_used, model_tier, tokens_in, tokens_out, cost_usd, latency_ms, cache_tier_hit, confidence)
  - [ ] `token_usage` (user_id, date, tier_1_tokens, tier_2_tokens, tier_3_tokens, total_cost)
  - [ ] `feedback` (query_log_id, rating, correction_text, timestamp)
  - [ ] `ingestion_log` (document_id, timestamp, status, chunks_created, duration_ms, error_message)
- [ ] **T-4.4.2** Log every query to `query_log` with full trace — **P1** `[FR-5.2]`
- [ ] **T-4.4.3** Aggregate daily token usage per user per tier — **P1**
- [ ] **T-4.4.4** Log every ingestion event to `ingestion_log` — **P1**

### 4.5 Token Budget & Cost Controls

- [ ] **T-4.5.1** Implement configurable token budget limits (daily / monthly), separate per tier — **P1** `[FR-4.10]`
- [ ] **T-4.5.2** Enforce budget: block Tier 3 queries when OpenAI budget exhausted, fall back to Tier 2 — **P1**
- [ ] **T-4.5.3** Add budget alert notifications at 50%, 80%, 100% thresholds (`st.toast`) — **P1**
- [ ] **T-4.5.4** Display real-time cost in admin dashboard — **P1**

### 4.6 Observability

- [ ] **T-4.6.1** Integrate `prometheus_client` — expose metrics endpoint — **P1**
- [ ] **T-4.6.2** Add metrics: cache hit rates (per tier), query latency histograms, token counts, ingestion duration — **P1**
- [ ] **T-4.6.3** Integrate OpenTelemetry Python SDK for distributed tracing — **P1** `[NFR-10]`
- [ ] **T-4.6.4** Add trace spans for: ingestion, cache lookup, retrieval, LLM call, post-processing — **P1**
- [ ] **T-4.6.5** Add health check endpoint that verifies all storage layers — **P1** `[FR-5.4]`

### 4.7 Security Hardening

- [ ] **T-4.7.1** Implement Streamlit session-based authentication (username + password) — **P1** `[PRD Section 17]`
- [ ] **T-4.7.2** Implement role-based authorization: Admin, Power User, Standard User — **P1**
- [ ] **T-4.7.3** Validate all file uploads: type allowlist, size limit, content sniffing — **P0**
- [ ] **T-4.7.4** Sanitize user query inputs (prevent prompt injection, XSS) — **P0**
- [ ] **T-4.7.5** Ensure OpenRouter API key is never logged or exposed — **P0**
- [ ] **T-4.7.6** Implement per-user query rate limiting — **P1**
- [ ] **T-4.7.7** Enable TLS for all external connections — **P1**
- [ ] **T-4.7.8** Security audit: review OWASP Top 10 alignment — **P1**

### 4.8 Error Handling & Resilience

- [ ] **T-4.8.1** Implement circuit breaker on OpenRouter API calls (trip after N failures → serve from cache) — **P1**
- [ ] **T-4.8.2** Implement graceful degradation: if vector store is down → inform user; if LLM is down → serve cache only — **P1** `[NFR-7]`
- [ ] **T-4.8.3** Implement dead letter queue for failed document ingestions (retry later) — **P2**
- [ ] **T-4.8.4** Add per-operation timeouts: embedding 30s, LLM 60s, ingestion 300s — **P1**

### 4.9 Production Configuration

- [ ] **T-4.9.1** Create production `docker-compose.prod.yml` with Qdrant, PostgreSQL, Redis Stack — **P0**
- [ ] **T-4.9.2** Migrate vector store to Qdrant (change config, verify abstraction layer works) — **P1**
- [ ] **T-4.9.3** Migrate metadata DB to PostgreSQL (run Alembic migration) — **P1**
- [ ] **T-4.9.4** Configure Redis Sentinel or Cluster for HA — **P2**
- [ ] **T-4.9.5** Add persistent named volumes for all data stores — **P0**
- [ ] **T-4.9.6** Write production deployment documentation — **P1**

### 4.10 Testing & Performance

- [ ] **T-4.10.1** Achieve >= 80% code coverage — **P1** `[NFR-8]`
- [ ] **T-4.10.2** Load test: 50 concurrent users, measure P95 latency — **P1** `[NFR-5]`
- [ ] **T-4.10.3** Benchmark: cache hit latency < 500ms at P95 — **P1** `[NFR-2]`
- [ ] **T-4.10.4** Benchmark: cache miss latency < 5s at P95 — **P1** `[NFR-1]`
- [ ] **T-4.10.5** Test ingestion throughput: >= 50 pages/minute — **P1** `[NFR-3]`
- [ ] **T-4.10.6** Test with 10,000+ documents to verify no retrieval quality degradation — **P2** `[G6]`

### 4.11 CI/CD

- [ ] **T-4.11.1** Create GitHub Actions workflow: lint (`ruff`), type-check (`mypy`), test (`pytest`), coverage report — **P1**
- [ ] **T-4.11.2** Add Docker image build and push to registry — **P1**
- [ ] **T-4.11.3** Add pre-commit hook configuration file — **P1**

---

## Phase 5: Enhancements (Weeks 13+)

### 5.1 Multi-Collection Support

- [ ] **T-5.1.1** Allow users to create named document collections (e.g., "Legal", "Engineering") — **P2** `[Enhancement 1]`
- [ ] **T-5.1.2** Support querying within a specific collection or across all collections — **P2**
- [ ] **T-5.1.3** Add collection-level access controls — **P2**
- [ ] **T-5.1.4** Update UI: collection picker in Document Manager and Chat — **P2**

### 5.2 Agentic RAG

- [ ] **T-5.2.1** Implement multi-step reasoning: decompose complex queries into sub-queries — **P2** `[Enhancement 2]`
- [ ] **T-5.2.2** Add tool-use support (calculator, date parser) when document context is insufficient — **P2**
- [ ] **T-5.2.3** Implement self-reflection: LLM evaluates answer quality, retries if confidence is low — **P2**

### 5.3 Feedback Loop & Active Learning

- [ ] **T-5.3.1** Add thumbs up/down buttons on each response — **P2** `[Enhancement 3]`
- [ ] **T-5.3.2** Add explicit correction mechanism ("The answer should be...") — **P2**
- [ ] **T-5.3.3** Store feedback in audit DB (`feedback` table) — **P2**
- [ ] **T-5.3.4** Use feedback to adjust cache prioritization (cache highly-rated responses longer) — **P2**
- [ ] **T-5.3.5** Periodic evaluation against golden QA dataset — **P2**

### 5.4 Scheduled Ingestion

- [ ] **T-5.4.1** Watch folder / S3 bucket for new documents, auto-ingest — **P2** `[Enhancement 4]`
- [ ] **T-5.4.2** Automatic re-indexing on document modification — **P2**
- [ ] **T-5.4.3** Webhook support for integration with document management systems — **P2**

### 5.5 Advanced Analytics

- [ ] **T-5.5.1** Topic clustering across the document corpus — **P2** `[Enhancement 5]`
- [ ] **T-5.5.2** Question trend analysis (most-asked topics) — **P2**
- [ ] **T-5.5.3** Knowledge gap detection (questions with low-confidence answers) — **P2**
- [ ] **T-5.5.4** Document coverage analysis (which docs are never retrieved?) — **P2**

### 5.6 Multi-Modal RAG

- [ ] **T-5.6.1** Image extraction from documents (charts, diagrams) with vision model support — **P2** `[Enhancement 6]`
- [ ] **T-5.6.2** Audio/video transcription via Whisper integration — **P2**
- [ ] **T-5.6.3** Table extraction with structure preservation — **P2**

### 5.7 Collaborative Features

- [ ] **T-5.7.1** Shared conversations with team members — **P2** `[Enhancement 7]`
- [ ] **T-5.7.2** Pinned / bookmarked answers — **P2**
- [ ] **T-5.7.3** Document annotation (highlight + comment) — **P2**

### 5.8 Local / Offline Mode

- [ ] **T-5.8.1** Integrate `ollama` as alternative LLM backend for fully local execution — **P2** `[Enhancement 8]`
- [ ] **T-5.8.2** Add config toggle: `LLM_BACKEND=openrouter|ollama` — **P2**
- [ ] **T-5.8.3** Test with air-gapped deployment (no internet) — **P2**

### 5.9 URL-Based Ingestion

- [ ] **T-5.9.1** Implement web page crawler (fetch URL, extract content, index) — **P2** `[FR-1.10]`
- [ ] **T-5.9.2** Add URL input field to Document Upload page — **P2**

### 5.10 Cache Warm-Up

- [ ] **T-5.10.1** Identify frequently asked questions from query log — **P2** `[FR-3.8]`
- [ ] **T-5.10.2** Pre-compute and cache answers for top FAQs on a schedule — **P2**

### 5.11 Structured Queries

- [ ] **T-5.11.1** Detect structured query intent ("compare X and Y") — **P2** `[FR-2.9]`
- [ ] **T-5.11.2** Implement multi-document comparison prompt template — **P2**

---

## Summary

| Phase | Tasks | P0 | P1 | P2 |
|-------|-------|----|----|-----|
| **Phase 1** — Foundation | 47 | 30 | 15 | 2 |
| **Phase 2** — Core RAG | 42 | 27 | 13 | 2 |
| **Phase 3** — Enterprise Caching | 27 | 17 | 10 | 0 |
| **Phase 4** — Polish & Production | 45 | 6 | 34 | 5 |
| **Phase 5** — Enhancements | 27 | 0 | 0 | 27 |
| **Total** | **188** | **80** | **72** | **36** |

### Critical Path (P0 tasks in sequence)

```
Project scaffold → Config & logging → Storage layer (file + DB + vector)
    → Parsers (PDF, DOCX, TXT, CSV) → Chunker → Embedder
    → Ingestion pipeline end-to-end → Basic Streamlit UI (upload + chat)
    → OpenRouter client → Complexity classifier → Tier routing
    → Retriever (dense search + context assembly) → Prompt builder
    → Full RAG pipeline → Multi-turn conversation → "I don't know" fallback
    → Redis setup → Exact-match cache → Semantic cache → Embedding cache
    → Cache invalidation → Cache integration into RAG pipeline
    → File upload validation → Input sanitization → Production Docker config
```
