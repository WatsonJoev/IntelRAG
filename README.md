# IntelRAG

Enterprise RAG AI platform: upload documents, ask questions, get cited answers. Built with Python, Streamlit, OpenRouter, and multi-tier caching.

## Features

- **Multi-format ingestion** — PDF, DOCX, TXT, CSV, XLSX, PPTX, HTML, JSON, XML, MD
- **RAG pipeline** — recursive chunking, local embeddings (sentence-transformers), vector search, LLM generation with citations
- **Complexity-based model routing** — Simple → Llama 3.1 (free), Moderate → Gemini Flash (free), Complex → GPT-4o-mini, with automatic fallback chain
- **Three-tier caching** — Tier 1 exact-match (SHA-256, 24 h), Tier 2 semantic similarity (cosine, 48 h), Tier 3 embedding cache — powered by fakeredis in dev
- **Multi-turn conversations** — session history persisted in SQLite, configurable context window
- **Audit logging** — per-query token usage, cost tracking, and ingestion logs stored in DB
- **Admin dashboard** — live KPIs, cost breakdown, cache hit rates, searchable query log, component health
- **Pluggable backends** — ChromaDB or Qdrant (vector), SQLite or PostgreSQL (metadata), local disk or S3/MinIO (files), fakeredis or Redis Stack (cache)

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

---

## Docker Compose

```bash
cp .env.example .env
# Set OPENROUTER_API_KEY in .env

# Dev profile — SQLite + ChromaDB (no extra services needed)
docker compose --profile dev up -d

# Full profile — PostgreSQL + Qdrant + Redis Stack
docker compose --profile full up -d
```

| Service | URL |
|---------|-----|
| App | http://localhost:8501 |
| Qdrant | http://localhost:6333 |
| Redis | localhost:6379 |

---

## Key environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | — | **Required.** OpenRouter gateway key |
| `DATABASE_URL` | `sqlite:///./data/intelrag.db` | Metadata DB (SQLite or PostgreSQL) |
| `VECTOR_STORE_BACKEND` | `chromadb` | `chromadb` or `qdrant` |
| `FILE_STORE_BACKEND` | `local` | `local`, `minio`, or `s3` |
| `REDIS_URL` | — | Leave blank in dev to use fakeredis |
| `TIER_1_MODEL` | `meta-llama/llama-3.1-8b-instruct:free` | Free-tier model (simple queries) |
| `TIER_2_MODEL` | `google/gemini-2.0-flash-exp:free` | Mid-tier model (moderate queries) |
| `TIER_3_MODEL` | `openai/gpt-4o-mini` | Premium model (complex queries) |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Local embedding model |
| `CHUNK_SIZE` | `1000` | Characters per chunk |
| `TOP_K_RERANK` | `5` | Chunks passed to LLM |
| `SIMILARITY_THRESHOLD` | `0.7` | Min retrieval score (0–1) |

See `.env.example` for the full list.

---

## Project layout

```
app/
  main.py              # Streamlit entry point + sidebar nav
  pages/
    documents.py       # Document manager (upload, browse, filter)
    chat.py            # Chat UI with RAG pipeline, badges, source cards
    admin.py           # Admin dashboard (KPIs, costs, cache, health)
core/
  schemas.py           # Shared dataclasses (RetrievedChunk, QueryResult)
  retriever.py         # Dense vector search + similarity filter
  prompt_builder.py    # System prompt + citation format + history
  confidence.py        # Chunk signals → LOW / MEDIUM / HIGH
  complexity_classifier.py  # Query → Tier enum + model_id
  llm_service.py       # OpenRouter client, retry+backoff, cost estimate
  audit.py             # log_query / log_ingestion helpers
  health.py            # check_all() — ChromaDB, SQLite, cache, OpenRouter
  cache/
    cache_manager.py   # 3-tier cache orchestration
    redis_client.py    # fakeredis (dev) / Redis Stack (prod) wrapper
  storage/
    vector_store.py    # VectorStoreProtocol + ChromaDB / Qdrant backends
    file_store.py      # Local / S3 / MinIO backends
ingestion/
  pipeline.py          # Orchestrator: hash → parse → chunk → embed → store
  chunker.py           # Recursive text chunker
  parsers/             # PDF, DOCX, TXT, CSV, XLSX, PPTX, HTML, JSON, XML
models/
  db.py                # SQLAlchemy ORM: Document, Chunk, Conversation,
                       #   QueryLog, TokenUsage, IngestionLog
config/
  settings.py          # Pydantic BaseSettings with env profiles
tests/                 # Pytest suite (43 tests)
```

---

## Running tests

```bash
pytest                 # Full suite
pytest -v              # Verbose
pytest --cov           # With coverage (80% target)
```

---

## Code quality

```bash
ruff check .           # Lint
ruff format .          # Format
mypy .                 # Type check
pre-commit run --all-files
```

---

## License

MIT
