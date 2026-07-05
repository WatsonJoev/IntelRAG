# IntelRAG

Enterprise RAG (Retrieval-Augmented Generation) platform: upload documents, ask questions, get cited answers with confidence scores and full cost/audit tracking. Built with Python, Streamlit, FastAPI + htmx, sentence-transformers, and OpenRouter.

## Features

- **Multi-format ingestion** — PDF, DOCX, TXT, CSV, XLSX, PPTX, HTML, JSON, XML, MD
- **RAG pipeline** — recursive chunking, local embeddings (sentence-transformers), vector search with similarity filtering, LLM generation with inline `[Source N]` citations
- **Complexity-based model routing** — queries are classified Simple / Moderate / Complex and routed to a matching model tier, with an automatic fallback chain when a tier is unavailable
- **Three-tier caching** — Tier 1 exact-match (SHA-256, 24 h), Tier 2 semantic similarity (cosine ≥ 0.95, 48 h), Tier 3 embedding cache — fakeredis in dev, Redis Stack in prod
- **Confidence scoring** — retrieval signals mapped to LOW / MEDIUM / HIGH badges on every answer
- **Multi-turn conversations** — session history persisted in the metadata DB with a configurable context window
- **Audit logging** — per-query model, tokens, cost, latency, cache tier, and confidence; per-document ingestion logs; daily token/cost rollups
- **Admin dashboard** — live KPIs, cost breakdown by tier, cache hit rates, searchable query log, component health
- **Two front-ends, one pipeline** — Streamlit (v1) and FastAPI + htmx (v2) both call the same `core.rag_service.answer_query()`
- **Pluggable backends** — ChromaDB or Qdrant (vectors), SQLite or PostgreSQL (metadata), local disk or S3/MinIO (files), fakeredis or Redis Stack (cache)

---

## System architecture

```
                        ┌────────────────────────────────────────────┐
                        │                Front-ends                  │
                        │  Streamlit (app/)      FastAPI+htmx (web/) │
                        └────────────┬───────────────────┬───────────┘
                                     │    shared service │
                                     ▼                   ▼
                        ┌────────────────────────────────────────────┐
                        │        core/rag_service.answer_query       │
                        │  classify → cache → retrieve → LLM →       │
                        │  confidence → cache store → audit          │
                        └──┬────────┬──────────┬──────────┬──────────┘
                           │        │          │          │
              ┌────────────▼──┐  ┌──▼───────┐ ┌▼────────┐ ┌▼─────────────┐
              │ CacheManager  │  │Retriever │ │ LLM svc │ │ Audit logger │
              │ 3-tier Redis  │  │ (dense   │ │ (Open-  │ │ (QueryLog,   │
              │ (fakeredis    │  │  vector  │ │ Router, │ │ TokenUsage,  │
              │  in dev)      │  │  search) │ │ retry + │ │ IngestionLog)│
              └───────────────┘  └────┬─────┘ │fallback)│ └──────┬───────┘
                                      │       └─────────┘        │
                                 ┌────▼─────────┐         ┌──────▼───────┐
                                 │ Vector store │         │ Metadata DB  │
                                 │ ChromaDB /   │         │ SQLite /     │
                                 │ Qdrant       │         │ PostgreSQL   │
                                 └──────────────┘         └──────────────┘
```

### Ingestion flow

```
Upload → ingestion/pipeline.py
  1. SHA-256 content hash → duplicate check against Document table (skip if seen)
  2. FileStore.save()      → raw file at {FILE_STORE_PATH}/{doc_id}/{filename}
  3. Parser factory        → format detected by content + extension (PDF, DOCX, …)
  4. Recursive chunker     → CHUNK_SIZE chars with CHUNK_OVERLAP, capped at MAX_CHUNKS_PER_DOC
  5. Embedding service     → sentence-transformers all-MiniLM-L6-v2 (384-dim, local, batched)
  6. Vector store          → ids, embeddings, chunk text, metadata (doc_id, page, offset)
  7. Metadata DB           → Document + Chunk rows, status = indexed
Failures are isolated per document (status = failed, logged to IngestionLog);
other documents keep processing.
```

### Query flow

```
Question → core/rag_service.answer_query()
  1. Complexity classifier → Tier (SIMPLE / MODERATE / COMPLEX)
  2. Doc-set hash          → cache keys are scoped to the current indexed corpus
  3. Cache lookup          → Tier 1 exact hash hit, else Tier 2 semantic hit → return cached
  4. Retrieval             → embed query, TOP_K_RETRIEVAL nearest chunks,
                             filter by SIMILARITY_THRESHOLD, keep TOP_K_RERANK
  5. Prompt builder        → system prompt + [Source N] context blocks + chat history
  6. LLM call              → tier model via OpenRouter; on failure walk the fallback
                             chain (Tier 1 → 2 → 3) with retry + exponential backoff
  7. Confidence score      → chunk score signals → LOW / MEDIUM / HIGH
  8. Cache store + audit   → QueryLog row (model, tokens, cost, latency, cache tier)
```

### Model routing tiers

| Tier | Query class | Default model | Cost |
|------|-------------|---------------|------|
| 1 | Simple (short, factual) | `meta-llama/llama-3.2-3b-instruct:free` | Free |
| 2 | Moderate | `meta-llama/llama-3.3-70b-instruct:free` | Free |
| 3 | Complex (analytical, multi-part) | `openai/gpt-4o-mini` | Paid |

If a tier's model is unavailable after retries, the request falls through to the next tier and the answer is badged `fallback`.

### Module responsibilities

```
app/                     Streamlit UI (v1)
  main.py                Entry point + sidebar navigation
  views/                 documents.py (upload/manage), chat.py, admin.py
web/                     FastAPI + htmx UI (v2) — server-rendered, no build step
  server.py              Routes: /v2/chat, /v2/documents, /v2/admin, /healthz
  templates/             Jinja2 (autoescaped) + Tailwind + htmx
core/
  rag_service.py         Shared RAG orchestration used by both front-ends
  retriever.py           Dense vector search + similarity filter
  prompt_builder.py      System prompt + citation format + history window
  complexity_classifier.py  Query → Tier enum + model id
  confidence.py          Chunk signals → LOW / MEDIUM / HIGH
  llm_service.py         OpenRouter client, retry+backoff, cost estimation
  audit.py               log_query / log_ingestion helpers
  health.py              check_all() — vector store, DB, cache, OpenRouter
  cache/                 3-tier cache manager + Redis/fakeredis wrapper
  storage/               VectorStore (ChromaDB/Qdrant), FileStore (local/S3/MinIO)
ingestion/
  pipeline.py            Orchestrator: hash → parse → chunk → embed → store
  chunker.py             Recursive text chunker
  parsers/               Format parsers behind a content-sniffing factory
models/
  db.py                  SQLAlchemy ORM: Document, Chunk, Collection, Conversation,
                         Config, QueryLog, TokenUsage, IngestionLog
  session.py             Engine, session factory, init_db()
config/
  settings.py            Pydantic BaseSettings (env profiles: development/staging/production)
  logging_config.py      structlog JSON logging
tests/                   Pytest suite (unit + integration; fakeredis + in-memory SQLite fixtures)
```

### Pluggable backends

| Layer | Dev (default) | Prod | Switch |
|-------|---------------|------|--------|
| Vector DB | ChromaDB (embedded) | Qdrant | `VECTOR_STORE_BACKEND` |
| Metadata DB | SQLite | PostgreSQL | `DATABASE_URL` |
| File store | Local disk | S3 / MinIO | `FILE_STORE_BACKEND` |
| Cache | fakeredis (in-process) | Redis Stack | `REDIS_URL` + `ENVIRONMENT` |

---

## Security posture

Current guardrails and their status — see **[docs/SECURITY_REVIEW.md](docs/SECURITY_REVIEW.md)** for the full review.

**In place today**

- All DB access through the SQLAlchemy ORM with bound parameters (no raw SQL)
- LLM output rendered as markdown with raw HTML escaped (XSS-safe answer rendering in v2); Jinja autoescaping on
- Server-generated document IDs and filename sanitization before anything touches disk
- Secrets only via environment / `.env` (gitignored); no credentials in the repo
- Per-query audit trail: model, tokens, cost, latency, cache tier, confidence
- LLM retry with exponential backoff + jitter, tier fallback, per-document ingestion failure isolation
- SHA-256 content hashing for duplicate detection

**Not yet in place — required before production exposure**

- **Authentication / RBAC** — all pages and APIs (including admin and document delete) are currently anonymous, single-tenant
- **Rate limiting and upload size enforcement on the FastAPI surface** (`MAX_FILE_SIZE_MB` is enforced in the Streamlit UI only; `QUERY_RATE_LIMIT_PER_USER` is not yet wired up)
- **CSRF tokens** on state-changing v2 endpoints
- **TLS + hardened session cookies**, security headers / CSP, SRI-pinned assets
- **Unified deletion** across DB + vectors + files + cache
- **Prompt-injection guardrails** for untrusted document content
- Non-root container, internal-only Docker service ports, DB/Redis/Qdrant auth

Deploy behind a reverse proxy with TLS and an authenticating gateway (e.g. oauth2-proxy) until native auth lands.

---

## Quick start — local (no Docker)

### 1. Clone and create a virtual environment

```bash
git clone <repo-url>
cd IntelRAG

python -m venv venv
# Windows
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -e ".[dev]"
```

### 3. Configure environment

```bash
# Windows
copy .env.example .env
# Linux / macOS
cp .env.example .env
```

Open `.env` and set your OpenRouter API key (get one free at https://openrouter.ai):

```
OPENROUTER_API_KEY=sk-or-v1-...
```

Everything else works with defaults for local dev (SQLite, ChromaDB, local file store, fakeredis).

### 4. Initialise the database

```bash
python -c "from models import init_db; from models.session import ensure_data_dir; ensure_data_dir(); init_db()"
```

### 5. Run the app

```bash
streamlit run app/main.py
```

Open **http://localhost:8501**

### 6. (Optional) Run the v2 UI — FastAPI + htmx

A lightweight, server-rendered alternative to Streamlit that reuses the exact
same RAG pipeline (`core.rag_service`). No Node/build step — Tailwind + htmx load
from a CDN.

```bash
uvicorn web.server:app --reload --port 8600
```

Open **http://localhost:8600/v2/chat** — routes: `/v2/chat`, `/v2/documents`,
`/v2/admin`, plus `/healthz` and OpenAPI docs at `/docs`.

---

## Docker Compose

```bash
cp .env.example .env
# Set OPENROUTER_API_KEY in .env

# Dev profile — SQLite + ChromaDB (no extra services needed)
docker compose --profile dev up -d

# Full profile — Redis Stack + Qdrant + PostgreSQL
docker compose --profile full up -d
```

| Service | URL |
|---------|-----|
| App | http://localhost:8501 |
| Qdrant | http://localhost:6333 |
| Redis | localhost:6379 |
| PostgreSQL | localhost:5432 |

> **Note:** the compose file is a development topology — service ports are
> published to the host without authentication, and the app container runs as
> root. Harden per [docs/SECURITY_REVIEW.md](docs/SECURITY_REVIEW.md) before any
> shared deployment.

---

## Key environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | — | **Required.** OpenRouter gateway key |
| `ENVIRONMENT` | `development` | `development` / `staging` / `production` profile |
| `DATABASE_URL` | `sqlite:///./data/intelrag.db` | Metadata DB (SQLite or PostgreSQL) |
| `VECTOR_STORE_BACKEND` | `chromadb` | `chromadb` or `qdrant` |
| `FILE_STORE_BACKEND` | `local` | `local`, `minio`, or `s3` |
| `REDIS_URL` | — | Leave blank in dev to use fakeredis |
| `TIER_1_MODEL` | `meta-llama/llama-3.2-3b-instruct:free` | Free-tier model (simple queries) |
| `TIER_2_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` | Mid-tier model (moderate queries) |
| `TIER_3_MODEL` | `openai/gpt-4o-mini` | Premium model (complex queries) |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Local embedding model (384-dim) |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `1000` / `200` | Chunking (characters) |
| `TOP_K_RETRIEVAL` / `TOP_K_RERANK` | `20` / `5` | Candidates fetched / chunks passed to LLM |
| `SIMILARITY_THRESHOLD` | `0.3` | Min retrieval score (0–1) |
| `CACHE_EXACT_TTL` / `CACHE_SEMANTIC_TTL` | `86400` / `172800` | Cache TTLs (seconds) |
| `MAX_FILE_SIZE_MB` | `200` | Upload cap (enforced in Streamlit UI) |
| `LOG_LEVEL` / `LOG_JSON` | `INFO` / `true` | structlog configuration |

See `.env.example` for the full list.

---

## Observability

- **Structured logs** — structlog JSON events (`document_indexed`, `llm_success`, `llm_retry`, `ingestion_failed`, …)
- **Query audit** — every question logged to `query_log` with model, tier, tokens in/out, estimated cost, latency, cache tier hit, confidence
- **Cost tracking** — daily rollups in `token_usage` by tier; surfaced on the admin dashboard
- **Health** — `core.health.check_all()` pings vector store, metadata DB, cache, and OpenRouter; exposed at `/healthz` (v2) and on the admin page

---

## Running tests

```bash
pytest                 # Full suite
pytest -v              # Verbose
pytest --cov           # With coverage (80% target)
```

Fixtures in `tests/conftest.py` provide an in-memory SQLite session, a fakeredis client, and a temporary file-store directory — no external services needed.

---

## Code quality

```bash
ruff check .           # Lint
ruff format .          # Format
mypy .                 # Type check (strict)
pre-commit run --all-files
```

---

## License

MIT
