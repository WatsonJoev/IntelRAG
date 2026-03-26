# IntelRAG

Enterprise RAG AI platform: upload documents, ask questions, get cited answers. Built with Python, Streamlit, OpenRouter, and multi-tier caching.

## Features

- **Multi-format document upload** — PDF, DOCX, TXT, CSV, MD, and more
- **RAG pipeline** — chunking, embeddings (local or API), vector search, LLM generation
- **OpenRouter gateway** — single API for Free / Gemini / OpenAI model tiers
- **Complexity-based routing** — Simple → Free models, Moderate → Gemini, Complex → OpenAI
- **Three-tier caching** — exact-match, semantic, and embedding cache (Redis)
- **Streamlit UI** — Document Manager, Chat, Admin Dashboard

## Quick start

### Local (no Docker)

```bash
# Clone and enter project
cd IntelRAG

# Create venv and install
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -e ".[dev]"

# Copy env and set OpenRouter key
copy .env.example .env
# Edit .env: set OPENROUTER_API_KEY=sk-or-v1-...

# Init DB and run
python -c "from models import init_db; from models.session import ensure_data_dir; ensure_data_dir(); init_db()"
streamlit run app/main.py
```

Open http://localhost:8501

### Docker Compose

```bash
cp .env.example .env
# Set OPENROUTER_API_KEY in .env
docker compose --profile full up -d
# App: http://localhost:8501, Redis: 6379, Qdrant: 6333
```

## Project layout

- `app/` — Streamlit pages (main.py, document manager, chat, admin)
- `core/` — RAG engine, cache, LLM service, storage (file, vector)
- `ingestion/` — Parsers, chunker, pipeline
- `models/` — SQLAlchemy ORM and DB session
- `config/` — Settings (pydantic-settings), logging (structlog)
- `tests/` — Pytest suite

## Tasks

See [Tasks.md](./Tasks.md) for the full task list derived from the PRD. Run tests: `pytest`.

## License

MIT
