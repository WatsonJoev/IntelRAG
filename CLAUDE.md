# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

IntelRAG is an enterprise RAG (Retrieval-Augmented Generation) platform. Users upload documents → they are parsed, chunked, embedded, and stored in a vector DB → a chat interface retrieves relevant chunks and sends them to an LLM via OpenRouter for context-aware answers.

**Current status**: Phase 1 (Foundation) is ~94% complete. Phase 2 (LLM integration via OpenRouter) is next.

## Commands

### Local Development (no Docker)
```bash
pip install -e ".[dev]"
streamlit run app/main.py          # App at http://localhost:8501
```

### Docker
```bash
cp .env.example .env               # Set OPENROUTER_API_KEY
docker compose --profile dev up -d    # SQLite + ChromaDB
docker compose --profile full up -d   # PostgreSQL + Qdrant + Redis
```

### Testing
```bash
pytest                             # Full suite
pytest tests/test_chunker.py -v   # Single test file
pytest --cov                       # With coverage (80% target)
```

### Code Quality
```bash
ruff check .                       # Lint
ruff format .                      # Format
mypy .                             # Type check (strict mode)
pre-commit run --all-files        # All hooks
```

## Architecture

### Data Flow
```
Upload → ingestion/pipeline.py → parsers/ → chunker.py → embedding_service.py → vector_store.py
                                                                                → models/db.py (metadata)
                                                                                → file_store.py (raw files)
Chat → vector search → top-K chunks → LLM (OpenRouter, Phase 2) → streamed response
```

### Module Responsibilities
- **`app/`** — Streamlit UI (document upload page, chat page)
- **`ingestion/`** — Pipeline orchestrator, parsers (PDF/DOCX/TXT/CSV/XLSX via factory), recursive text chunker
- **`core/`** — Embedding service (sentence-transformers `all-MiniLM-L6-v2`, 384-dim), vector store abstraction (ChromaDB dev / Qdrant prod), file store abstraction (local / S3 / MinIO)
- **`models/`** — SQLAlchemy ORM: `Document`, `Chunk`, `Collection`, `Conversation`, `Config` tables; SQLite (dev) / PostgreSQL (prod)
- **`config/`** — Pydantic `BaseSettings` with env profiles (`development`, `staging`, `production`); structlog JSON logging with correlation IDs

### Pluggable Backends (controlled via env vars)
| Layer | Dev | Prod |
|-------|-----|------|
| Vector DB | ChromaDB (`VECTOR_STORE_BACKEND=chromadb`) | Qdrant (`VECTOR_STORE_BACKEND=qdrant`) |
| Metadata DB | SQLite | PostgreSQL |
| File Store | Local disk (`FILE_STORE_BACKEND=local`) | S3/MinIO |
| Cache | None / fakeredis | Redis Stack |

### Key Design Points
- **Duplicate detection**: SHA-256 hashing in `ingestion/pipeline.py` prevents re-ingesting the same file
- **Ingestion resilience**: Failed documents are marked `status=failed` in DB; processing continues for remaining docs
- **Caching (planned Phase 3)**: 3-tier Redis caching — exact-match, semantic similarity, embedding cache
- **LLM routing (planned Phase 2)**: Query complexity classifier routes to model tiers: free (Llama-3.1) → Gemini → GPT-4o-mini

## Environment Variables

Key vars (see `.env.example` for full list):
- `OPENROUTER_API_KEY` — required for LLM calls
- `DATABASE_URL` — defaults to `sqlite:///./data/intelrag.db`
- `VECTOR_STORE_BACKEND` — `chromadb` (default) or `qdrant`
- `FILE_STORE_BACKEND` — `local` (default), `minio`, or `s3`
- `EMBEDDING_MODEL` — default `all-MiniLM-L6-v2`
- `CHUNK_SIZE`, `CHUNK_OVERLAP` — default 1000 / 200

## Test Fixtures

`tests/conftest.py` provides:
- In-memory SQLite DB session
- `fakeredis` Redis client (no real Redis needed)
- Temporary file store directory

Parsers, chunker, and file store have unit tests. Vector store and pipeline tests are integration-level.
