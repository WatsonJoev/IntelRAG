# IntelRAG — Enterprise RAG AI Platform

## Product Requirements Document (PRD)

| Field            | Value                                      |
| ---------------- | ------------------------------------------ |
| **Product Name** | IntelRAG                                   |
| **Version**      | 1.0                                        |
| **Author**       | Joev                                       |
| **Date**         | 2026-03-15                                 |
| **Status**       | Draft                                      |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [Target Users & Personas](#4-target-users--personas)
5. [System Architecture](#5-system-architecture)
6. [Functional Requirements](#6-functional-requirements)
7. [Non-Functional Requirements](#7-non-functional-requirements)
8. [Tech Stack](#8-tech-stack)
9. [Storage Architecture](#9-storage-architecture)
10. [Document Ingestion Pipeline](#10-document-ingestion-pipeline)
11. [RAG Pipeline Design](#11-rag-pipeline-design)
12. [Caching Strategy](#12-caching-strategy)
13. [OpenRouter AI Gateway Integration](#13-openrouter-ai-gateway-integration)
14. [Streamlit UI Specification](#14-streamlit-ui-specification)
15. [Enterprise Best Practices](#15-enterprise-best-practices)
16. [Cost Optimization Strategy](#16-cost-optimization-strategy)
17. [Security & Compliance](#17-security--compliance)
18. [Proposed Enhancements](#18-proposed-enhancements)
19. [Milestones & Roadmap](#19-milestones--roadmap)
20. [Risk Register](#20-risk-register)
21. [Glossary](#21-glossary)

---

## 1. Executive Summary

**IntelRAG** is an enterprise-grade Retrieval-Augmented Generation (RAG) platform built in Python. It allows users to upload any number and type of documents through a Streamlit web interface, intelligently indexes their content into a vector store, and provides accurate, context-aware AI responses powered by large language models accessed via the **OpenRouter AI Gateway**.

The platform implements a multi-tier caching architecture — semantic cache, embedding cache, and response cache — to dramatically reduce latency and API costs, making it viable for high-volume enterprise deployments.

---

## 2. Problem Statement

Organizations possess vast amounts of institutional knowledge locked inside documents (PDFs, Word files, spreadsheets, presentations, code, etc.). Existing solutions are either:

- **Too simplistic** — basic keyword search with no semantic understanding.
- **Too expensive** — every query triggers a full LLM call with no cost governance.
- **Too narrow** — limited to a single document type or small corpus sizes.
- **Not production-ready** — lack observability, caching, access controls, and audit trails.

IntelRAG solves these problems by providing a single platform that ingests heterogeneous documents, retrieves relevant context with high precision, answers questions via state-of-the-art LLMs, and caches intelligently to keep costs predictable.

---

## 3. Goals & Success Metrics

### Primary Goals

| # | Goal | Measure |
|---|------|---------|
| G1 | Accurate, context-grounded answers | Answer relevance score >= 0.85 (evaluated via RAGAS or similar) |
| G2 | Support heterogeneous document types | >= 12 file formats supported at launch |
| G3 | Sub-second cached responses | P95 latency < 500ms for cache hits |
| G4 | Cost efficiency | >= 60% reduction in LLM API spend via caching |
| G5 | Enterprise readiness | Pass internal security review; SOC 2 alignment |

### Secondary Goals

| # | Goal | Measure |
|---|------|---------|
| G6 | Scalable to 10,000+ documents | No degradation in retrieval quality at scale |
| G7 | Multi-user support | Concurrent sessions without cross-contamination |
| G8 | Observable system | End-to-end request tracing and cost dashboards |

---

## 4. Target Users & Personas

| Persona | Role | Needs |
|---------|------|-------|
| **Knowledge Worker** | Analyst, researcher, consultant | Upload reports, ask questions, get cited answers fast |
| **Engineering Team** | Developer, DevOps | Upload technical docs, RFCs, runbooks; query during incidents |
| **Leadership** | Manager, executive | Query summarized insights from large document collections |
| **Admin / IT** | System administrator | Manage users, monitor costs, configure models, audit usage |

---

## 5. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        STREAMLIT UI                             │
│  ┌──────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────┐ │
│  │ Document  │  │   Chat /     │  │  Admin     │  │ Analytics│ │
│  │ Upload    │  │   Query UI   │  │  Panel     │  │ Dashboard│ │
│  └─────┬────┘  └──────┬───────┘  └─────┬──────┘  └─────┬────┘ │
└────────┼───────────────┼────────────────┼───────────────┼──────┘
         │               │                │               │
         ▼               ▼                ▼               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER (Python)                 │
│                                                                 │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │ Ingestion  │  │  RAG Engine  │  │   Cache Manager        │  │
│  │ Pipeline   │  │  (Retrieve + │  │   (Semantic + Response │  │
│  │            │  │   Generate)  │  │    + Embedding Cache)  │  │
│  └─────┬──────┘  └──────┬───────┘  └────────────┬───────────┘  │
│        │                │                        │              │
│  ┌─────▼──────┐  ┌──────▼───────┐  ┌────────────▼───────────┐  │
│  │ Document   │  │  Retriever   │  │   Query Complexity      │  │
│  │ Parsers    │  │  (Vector +   │  │   Classifier            │  │
│  │ (per type) │  │   Hybrid)    │  │   (Free/Gemini/OpenAI)  │  │
│  └────────────┘  └──────────────┘  └────────────────────────┘  │
│                                                                 │
│  ┌────────────────────────────┐  ┌───────────────────────────┐  │
│  │ Embedding Service          │  │  LLM Service              │  │
│  │ (local or API)             │  │  (via OpenRouter Gateway)  │  │
│  └────────────────────────────┘  └───────────────────────────┘  │
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Observability: Logging · Tracing · Cost Tracking · Metrics │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
         │               │                │               │
         ▼               ▼                ▼               ▼
┌─────────────────────────────────────────────────────────────────┐
│                       STORAGE LAYER                             │
│                                                                 │
│  ┌───────────────┐ ┌───────────────┐ ┌────────────────────────┐ │
│  │ File Store    │ │ Vector Store  │ │  Cache Store (Redis)   │ │
│  │ (Local FS /   │ │ (ChromaDB /   │ │  ┌──────────────────┐ │ │
│  │  S3 / MinIO)  │ │  Qdrant)      │ │  │ Response Cache   │ │ │
│  │               │ │               │ │  │ Semantic Cache   │ │ │
│  │ Raw uploads + │ │ Embeddings +  │ │  │ Embedding Cache  │ │ │
│  │ parsed text   │ │ chunk vectors │ │  └──────────────────┘ │ │
│  └───────────────┘ └───────────────┘ └────────────────────────┘ │
│                                                                 │
│  ┌───────────────┐ ┌─────────────────────────────────────────┐  │
│  │ Metadata DB   │ │  Audit / Analytics Store                │  │
│  │ (SQLite /     │ │  (SQLite / PostgreSQL)                  │  │
│  │  PostgreSQL)  │ │  Query logs, token usage, cost records  │  │
│  └───────────────┘ └─────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                  ┌────────────────────────┐
                  │   OpenRouter AI         │
                  │   Gateway               │
                  │   ┌──────────────────┐  │
                  │   │ Free: Llama/     │  │
                  │   │   Mistral/Gemma  │  │
                  │   │ Mid:  Gemini     │  │
                  │   │ Top:  GPT-4o     │  │
                  │   └──────────────────┘  │
                  └────────────────────────┘
```

---

## 6. Functional Requirements

### FR-1: Document Upload & Management

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1.1 | Upload single or multiple documents simultaneously via drag-and-drop or file picker | P0 |
| FR-1.2 | Support file types: PDF, DOCX, DOC, XLSX, XLS, CSV, PPTX, TXT, MD, HTML, JSON, XML, EPUB, RTF, images (OCR), source code files | P0 |
| FR-1.3 | Display upload progress with per-file status (queued, processing, indexed, failed) | P0 |
| FR-1.4 | Automatic file type detection and routing to the appropriate parser | P0 |
| FR-1.5 | Document metadata extraction (title, author, page count, creation date, file size) | P1 |
| FR-1.6 | Document listing with search, filter, and delete capabilities | P1 |
| FR-1.7 | Batch upload via ZIP archive (auto-extract and process each file) | P2 |
| FR-1.8 | Duplicate detection based on content hash to avoid redundant indexing | P1 |
| FR-1.9 | Maximum file size: 200 MB per file; configurable per deployment | P0 |
| FR-1.10 | Support for URL-based ingestion (crawl a web page and index its content) | P2 |

### FR-2: Query & Conversation

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-2.1 | Natural language query input with chat-style interface | P0 |
| FR-2.2 | Multi-turn conversation with context memory (session-scoped) | P0 |
| FR-2.3 | Source citation: every answer must reference the source document(s), page number(s), and relevant excerpt(s) | P0 |
| FR-2.4 | Confidence score per answer (low / medium / high) displayed to user | P1 |
| FR-2.5 | "I don't know" fallback when retrieved context is insufficient (avoid hallucination) | P0 |
| FR-2.6 | Query rewriting / expansion for improved retrieval | P1 |
| FR-2.7 | Follow-up question suggestions based on context | P2 |
| FR-2.8 | Export conversation history as PDF or Markdown | P2 |
| FR-2.9 | Support for structured queries (e.g., "compare X and Y across documents") | P2 |

### FR-3: Caching

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-3.1 | Semantic cache: cache LLM responses keyed by semantic similarity of the query (not exact match) | P0 |
| FR-3.2 | Embedding cache: cache computed embeddings to avoid recomputation | P0 |
| FR-3.3 | Response cache: exact-match cache for identical queries against the same document set | P0 |
| FR-3.4 | Cache invalidation when underlying documents are added, modified, or deleted | P0 |
| FR-3.5 | Configurable TTL (time-to-live) per cache layer | P1 |
| FR-3.6 | Cache hit/miss metrics exposed in admin dashboard | P1 |
| FR-3.7 | Manual cache purge option for admins | P1 |
| FR-3.8 | Cache warm-up: pre-compute answers for frequently asked questions | P2 |

### FR-4: Model Management (via OpenRouter — Complexity-Based Routing)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-4.1 | Integrate with OpenRouter API as the unified gateway for all LLM access | P0 |
| FR-4.2 | **Automatic complexity-based model routing**: classify each query as Simple / Moderate / Complex and route to the corresponding model tier (see Model Tier Strategy below) | P0 |
| FR-4.3 | **Simple queries → OpenRouter Free models** (e.g., Llama 3.1 8B, Mistral 7B Instruct, Gemma 2 9B — all free-tier on OpenRouter) | P0 |
| FR-4.4 | **Moderate queries → Google Gemini** (e.g., Gemini 2.0 Flash, Gemini 2.0 Pro via OpenRouter) | P0 |
| FR-4.5 | **Complex queries → OpenAI** (e.g., GPT-4o, GPT-4o-mini via OpenRouter) | P0 |
| FR-4.6 | Model fallback chain: if the selected tier's model fails or is rate-limited, fall back to the next tier up (Free → Gemini → OpenAI) | P1 |
| FR-4.7 | Per-query model override: power users can manually select a specific model, bypassing the auto-router | P2 |
| FR-4.8 | Admin-configurable default model per tier (swap models within a tier without code changes) | P1 |
| FR-4.9 | Token usage tracking per query, per user, per session, **per model tier** | P0 |
| FR-4.10 | Configurable token budget limits (daily / monthly) with alerts; separate budgets per tier | P1 |
| FR-4.11 | Support for streaming responses (token-by-token display) across all three tiers | P1 |
| FR-4.12 | Query complexity classifier: lightweight rule-based + optional small local model to determine routing (must add < 100ms latency) | P0 |

### FR-5: Admin & Observability

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-5.1 | Admin dashboard: document count, query volume, cache hit rate, cost metrics | P1 |
| FR-5.2 | Query audit log with timestamp, user, query, model used, tokens consumed, latency, cache status | P1 |
| FR-5.3 | Structured logging (JSON) for all application events | P0 |
| FR-5.4 | Health check endpoint for monitoring | P1 |
| FR-5.5 | Configuration management via environment variables and/or YAML config | P0 |

---

## 7. Non-Functional Requirements

| ID | Category | Requirement | Target |
|----|----------|-------------|--------|
| NFR-1 | **Performance** | Query-to-answer latency (cache miss) | P95 < 5 seconds |
| NFR-2 | **Performance** | Query-to-answer latency (cache hit) | P95 < 500 ms |
| NFR-3 | **Performance** | Document ingestion throughput | >= 50 pages/minute |
| NFR-4 | **Scalability** | Document corpus size | Up to 100,000 documents |
| NFR-5 | **Scalability** | Concurrent users | >= 50 simultaneous sessions |
| NFR-6 | **Availability** | Uptime target | 99.5% (excluding scheduled maintenance) |
| NFR-7 | **Reliability** | Graceful degradation on LLM provider outage | Serve cached results; queue new queries |
| NFR-8 | **Maintainability** | Code coverage | >= 80% |
| NFR-9 | **Portability** | Containerized deployment | Docker + Docker Compose |
| NFR-10 | **Observability** | Distributed tracing | OpenTelemetry-compatible |

---

## 8. Tech Stack

### Core

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Language** | Python 3.11+ | Mature ML/AI ecosystem, async support |
| **UI Framework** | Streamlit 1.x | Rapid prototyping, built-in file upload, session state, chat UI |
| **RAG Orchestration** | LangChain or LlamaIndex | Battle-tested RAG abstractions, retriever/chain patterns |
| **Embeddings** | `sentence-transformers` (local) or OpenRouter API embeddings | Local = free & fast; API = higher quality for some domains |
| **Vector Store** | ChromaDB (dev/small) / Qdrant (production) | ChromaDB for simplicity; Qdrant for production scale (see Section 9) |
| **File Store** | Local filesystem (dev) / MinIO or S3 (production) | Raw uploads + parsed text; MinIO is S3-compatible & self-hosted |
| **Metadata DB** | SQLite (dev/single-node) / PostgreSQL (production) | Document metadata, user data, audit logs, analytics |
| **Cache Store** | Redis 7.x (primary) | Response cache, semantic cache, embedding cache — all in Redis |
| **Semantic Cache** | Redis + vector similarity (RediSearch) or GPTCache | Avoid redundant LLM calls for semantically similar queries |
| **LLM Gateway** | OpenRouter (`openai`-compatible SDK) | Single API key, access to 100+ models, built-in fallback |

### Document Parsers

| File Type | Parser Library |
|-----------|---------------|
| PDF | `PyMuPDF` (fitz) / `pdfplumber` |
| DOCX | `python-docx` |
| XLSX / CSV | `openpyxl` / `pandas` |
| PPTX | `python-pptx` |
| HTML | `BeautifulSoup4` |
| Markdown | `markdown` / `mistune` |
| Images (OCR) | `pytesseract` + `Pillow` |
| EPUB | `ebooklib` |
| JSON / XML | `json` / `lxml` |
| Source Code | `tree-sitter` / plain text with language detection |

### Infrastructure

| Component | Technology |
|-----------|-----------|
| Containerization | Docker + Docker Compose |
| Process Management | `supervisord` or Docker multi-service |
| Environment Config | `python-dotenv` / `pydantic-settings` |
| Logging | `structlog` (JSON structured logging) |
| Metrics | Prometheus client (`prometheus_client`) |
| Tracing | OpenTelemetry Python SDK |
| Testing | `pytest` + `pytest-asyncio` + `pytest-cov` |
| Linting | `ruff` (replaces flake8, isort, black) |
| Type Checking | `mypy` |

---

## 9. Storage Architecture

IntelRAG uses **five distinct storage layers**, each optimized for a specific data type and access pattern. The right storage choice at each layer is what makes the system fast for AI consumption and viable for caching at enterprise scale.

### Storage Layer Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        STORAGE LAYERS                               │
│                                                                     │
│  ┌─────────────┐  What is stored?            Access pattern         │
│  │ 1. FILE     │  Original uploaded files    Write-once, read-rare  │
│  │    STORE    │  (PDF, DOCX, etc.)          (re-download, re-parse)│
│  └──────┬──────┘                                                    │
│         │ parsed text flows down                                    │
│  ┌──────▼──────┐  Chunk text + embeddings    Write-once, read-heavy │
│  │ 2. VECTOR   │  (dense vectors for         (every query hits this)│
│  │    STORE    │   similarity search)                               │
│  └──────┬──────┘                                                    │
│         │ metadata links back                                       │
│  ┌──────▼──────┐  Doc metadata, chunk map,   Read/write moderate    │
│  │ 3. METADATA │  user data, config          (lookups, filters,     │
│  │    DB       │                              admin operations)     │
│  └─────────────┘                                                    │
│                                                                     │
│  ┌─────────────┐  Cached responses, cached   Read-heavy, auto-TTL  │
│  │ 4. CACHE    │  embeddings, semantic        (fastest layer — every │
│  │    STORE    │  cache index                 query checks this     │
│  └─────────────┘                              BEFORE vector store)  │
│                                                                     │
│  ┌─────────────┐  Query audit logs, token    Write-heavy, read for  │
│  │ 5. AUDIT /  │  usage, cost records,       analytics & compliance │
│  │    ANALYTICS│  feedback data                                     │
│  └─────────────┘                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

### Layer 1: File Store (Raw Document Storage)

Stores the **original uploaded files** exactly as the user provided them. Needed for re-downloading, re-parsing (if chunking strategy changes), and compliance/audit.

| Aspect | Development | Production |
|--------|------------|------------|
| **Technology** | Local filesystem (`./data/uploads/`) | **MinIO** (self-hosted, S3-compatible) or **AWS S3** |
| **Why this choice** | Zero setup; just a folder | MinIO is free, S3-compatible, supports versioning, lifecycle policies, and encryption at rest. No vendor lock-in. |
| **Structure** | `uploads/{doc_id}/{original_filename}` | `s3://intelrag-docs/{tenant_id}/{doc_id}/{filename}` |
| **Retention** | Keep indefinitely (dev) | Configurable lifecycle: archive to cold storage after 90 days |
| **Encryption** | None (dev) | AES-256 server-side encryption |
| **Size Limit** | 200 MB per file | 200 MB per file (configurable) |

**Why NOT store files in the database?** Binary blobs in PostgreSQL/SQLite bloat the DB, slow backups, and don't benefit from object storage features (CDN, lifecycle, versioning). Keep files in a file/object store; keep metadata in the DB.

### Layer 2: Vector Store (Embeddings + Chunks for AI Retrieval)

This is **the most critical store for AI consumption**. Every user query hits the vector store to find relevant chunks via embedding similarity search.

| Aspect | Development | Production | Why |
|--------|------------|------------|-----|
| **Technology** | **ChromaDB** (embedded, in-process) | **Qdrant** (dedicated server) | See comparison below |
| **What's stored** | Embedding vector + chunk text + metadata per chunk | Same | AI needs both the vector (for search) and the text (for LLM context) |
| **Metadata per chunk** | `doc_id`, `chunk_index`, `page_number`, `source_file`, `char_offset`, `timestamp` | Same | Enables citation, filtering, invalidation |
| **Index type** | HNSW (Hierarchical Navigable Small World) | HNSW with configurable `ef` and `m` | Best balance of speed and recall for ANN search |
| **Distance metric** | Cosine similarity | Cosine similarity | Standard for sentence embeddings |
| **Persistence** | Local directory (`./data/chroma/`) | Docker volume or dedicated disk | Must survive container restarts |

#### ChromaDB vs. Qdrant Decision Matrix

| Criteria | ChromaDB | Qdrant | Recommendation |
|----------|----------|--------|---------------|
| **Setup** | `pip install chromadb`; runs in-process | Docker container; client-server | ChromaDB for dev; Qdrant for prod |
| **Scale** | Good up to ~500K vectors | Proven at 100M+ vectors | Qdrant for enterprise |
| **Filtering** | Basic metadata filtering | Rich payload filtering with indexes | Qdrant for complex queries |
| **Performance** | ~10ms for 100K vectors | ~5ms for 1M+ vectors (with HNSW) | Qdrant at scale |
| **Multi-tenancy** | Collections | Collections + named vectors + payload indexes | Qdrant for multi-tenant |
| **Hybrid search** | Requires external BM25 | Built-in sparse+dense (v1.7+) | Qdrant avoids extra dependency |
| **Backup** | File copy | Snapshot API | Qdrant for ops |
| **Cost** | Free (embedded) | Free (self-hosted) or Qdrant Cloud ($) | Both free self-hosted |
| **Persistence** | SQLite + Parquet files | Custom storage engine, memory-mapped | Qdrant more production-hardened |

**Recommendation**: Start with **ChromaDB** for rapid development and local testing. Migrate to **Qdrant** before production. The LangChain/LlamaIndex abstraction layer makes this a config change, not a rewrite.

#### Vector Store Sizing Estimate

| Corpus Size | Chunks (est.) | Embedding Dimensions | Storage Required |
|------------|--------------|---------------------|-----------------|
| 500 docs | ~50,000 | 384 (MiniLM) | ~150 MB |
| 5,000 docs | ~500,000 | 384 (MiniLM) | ~1.5 GB |
| 50,000 docs | ~5,000,000 | 384 (MiniLM) | ~15 GB |
| 50,000 docs | ~5,000,000 | 1536 (OpenAI ada-002) | ~60 GB |

*Estimates include vector data + stored chunk text + metadata. Actual size depends on chunk size and document density.*

### Layer 3: Metadata Database (Document Registry + Application State)

Stores **structured relational data** that the vector store cannot efficiently handle: document metadata, user sessions, configuration, and cross-references.

| Aspect | Development | Production |
|--------|------------|------------|
| **Technology** | **SQLite** (`./data/intelrag.db`) | **PostgreSQL 16** |
| **Why** | Zero config, file-based, excellent for single-process | ACID, concurrent access, full-text search, JSON columns, battle-tested |
| **ORM** | `SQLAlchemy` or `SQLModel` (Pydantic + SQLAlchemy) | Same |
| **Migrations** | `Alembic` | Same |

#### Key Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `documents` | Document registry | `id`, `filename`, `file_type`, `file_size`, `content_hash`, `file_store_path`, `status`, `chunk_count`, `page_count`, `created_at` |
| `chunks` | Chunk-to-document mapping | `id`, `document_id`, `chunk_index`, `page_number`, `char_offset`, `vector_store_id`, `text_preview` |
| `collections` | Named document groups | `id`, `name`, `description`, `document_ids`, `created_by` |
| `conversations` | Chat session state | `id`, `user_id`, `messages_json`, `created_at`, `updated_at` |
| `config` | Runtime configuration | `key`, `value`, `updated_at`, `updated_by` |

**Why NOT just use the vector store for metadata?** Vector stores are optimized for ANN (approximate nearest neighbor) search, not relational queries. Filtering documents by date range, joining chunks to documents, counting records, or running admin queries is orders of magnitude faster in a relational DB.

### Layer 4: Cache Store (Redis — The Speed Layer)

Redis serves as the **unified cache layer** across all three cache tiers. It is the first thing the system checks on every query — before the vector store, before the LLM.

| Aspect | Detail |
|--------|--------|
| **Technology** | **Redis 7.x** with **RediSearch** module (for vector similarity in semantic cache) |
| **Development** | Docker Redis container or `fakeredis` for unit tests |
| **Production** | Redis Sentinel (HA) or Redis Cluster (scale) |
| **Why Redis for everything?** | Sub-millisecond reads, native TTL, pub/sub for invalidation, RediSearch adds vector similarity — one system for all three cache tiers |

#### What's stored in Redis

| Redis Structure | Purpose | Data Type | TTL |
|----------------|---------|-----------|-----|
| `cache:exact:{hash}` | Tier 1 — exact-match response cache | JSON string (answer + sources) | 24h |
| `cache:semantic:idx` | Tier 2 — semantic cache (RediSearch vector index) | Vector + JSON payload | 48h |
| `cache:embedding:{hash}` | Tier 3 — embedding cache | Binary (vector bytes) | Indefinite |
| `meta:doc_set_hash` | Current document corpus hash (for invalidation) | String | Indefinite |
| `stats:*` | Cache hit/miss counters, latency histograms | Sorted sets / HyperLogLog | Rolling 30d |
| `session:{id}` | Streamlit session state backup | JSON | 2h |

#### Why Redis over alternatives for caching?

| Alternative | Why Redis Wins |
|-------------|---------------|
| **Memcached** | No persistence, no TTL per key, no data structures, no vector search |
| **SQLite cache** | Disk-based = 10-100x slower than Redis for reads; no native TTL |
| **In-process dict / LRU** | Lost on restart; not shared across Streamlit worker processes |
| **DragonflyDB** | Redis-compatible but less mature; consider for extreme scale |

#### Redis Memory Sizing

| Cache Tier | Items (50K queries/month, 60% hit rate) | Avg. Item Size | Memory |
|-----------|----------------------------------------|---------------|--------|
| Exact-match | ~20,000 active entries | ~2 KB | ~40 MB |
| Semantic | ~15,000 vectors + responses | ~4 KB | ~60 MB |
| Embedding | ~500,000 chunk embeddings | ~1.5 KB (384-dim) | ~750 MB |
| **Total** | | | **~850 MB** |

A single Redis instance with 2 GB RAM handles a department-scale deployment comfortably. Enterprise scale (50K docs) needs 4–8 GB.

### Layer 5: Audit & Analytics Store

Stores **immutable logs** for compliance, cost tracking, and usage analytics. This data is write-heavy and append-only.

| Aspect | Development | Production |
|--------|------------|------------|
| **Technology** | SQLite (same DB as metadata, separate tables) | **PostgreSQL** (same instance, separate schema) or dedicated time-series DB |
| **Retention** | Keep all (dev) | 12 months hot, archive to cold storage |

#### Key Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `query_log` | Every query with full trace | `id`, `timestamp`, `user_id`, `query_text`, `model_used`, `model_tier`, `tokens_in`, `tokens_out`, `cost_usd`, `latency_ms`, `cache_tier_hit`, `confidence` |
| `token_usage` | Aggregated usage per user/day | `user_id`, `date`, `tier_1_tokens`, `tier_2_tokens`, `tier_3_tokens`, `total_cost` |
| `feedback` | User thumbs up/down + corrections | `query_log_id`, `rating`, `correction_text`, `timestamp` |
| `ingestion_log` | Document processing audit trail | `document_id`, `timestamp`, `status`, `chunks_created`, `duration_ms`, `error_message` |

### Storage Decision Summary

| Question | Answer | Why |
|----------|--------|-----|
| **Where do raw documents live?** | File store (local FS / MinIO / S3) | Object storage is purpose-built for files; cheap, scalable, versionable |
| **Where do chunks + embeddings live?** | Vector store (ChromaDB → Qdrant) | Optimized for ANN similarity search — the core AI retrieval operation |
| **Where does document metadata live?** | Relational DB (SQLite → PostgreSQL) | Relational queries, joins, filters, counts — things vector stores can't do well |
| **Where do cached responses live?** | Redis | Sub-millisecond reads, native TTL, vector search via RediSearch — ideal for all 3 cache tiers |
| **Where do audit logs live?** | Relational DB (same or separate PostgreSQL) | Structured, queryable, integrates with analytics dashboards |

### Storage in Docker Compose (Production)

```yaml
services:
  app:
    build: .
    volumes:
      - uploads:/data/uploads
    depends_on: [redis, qdrant, postgres]

  redis:
    image: redis/redis-stack:7.2.0-v6  # includes RediSearch
    volumes:
      - redis_data:/data
    command: redis-server --maxmemory 4gb --maxmemory-policy allkeys-lru

  qdrant:
    image: qdrant/qdrant:v1.9.0
    volumes:
      - qdrant_data:/qdrant/storage
    ports:
      - "6333:6333"

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: intelrag
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pg_data:/var/lib/postgresql/data

volumes:
  uploads:
  redis_data:
  qdrant_data:
  pg_data:
```

### Dev vs. Production Storage Matrix

| Layer | Development (Zero-Infra) | Production (Docker Compose) | Cloud (Managed) |
|-------|-------------------------|----------------------------|----------------|
| File Store | Local filesystem | MinIO container | AWS S3 / GCS |
| Vector Store | ChromaDB (embedded) | Qdrant (container) | Qdrant Cloud / Pinecone |
| Metadata DB | SQLite (file) | PostgreSQL (container) | AWS RDS / Supabase |
| Cache Store | `fakeredis` or local Redis | Redis Stack (container) | AWS ElastiCache / Upstash |
| Audit Store | SQLite (same file) | PostgreSQL (same instance) | Same as Metadata DB |

All production components run as Docker containers with persistent named volumes. The application code uses abstraction layers (SQLAlchemy, LangChain vector store interface, Redis client) so swapping between dev and production storage is a **config change, not a code change**.

---

## 10. Document Ingestion Pipeline

```
Upload (Streamlit)
    │
    ▼
File Type Detection (python-magic / mimetypes)
    │
    ▼
Duplicate Check (SHA-256 content hash)
    │
    ├── Duplicate found → Skip, link to existing index
    │
    ▼
Parser Selection (factory pattern per file type)
    │
    ▼
Text Extraction + Metadata Extraction
    │
    ▼
Text Cleaning & Normalization
    │  - Remove headers/footers/watermarks
    │  - Normalize whitespace and encoding
    │  - Language detection
    │
    ▼
Chunking Strategy
    │  - Recursive character splitting (default: 1000 chars, 200 overlap)
    │  - Semantic chunking (sentence-boundary aware)
    │  - Table-aware chunking (preserve table structures)
    │  - Code-aware chunking (respect function/class boundaries)
    │
    ▼
Embedding Generation
    │  - Check embedding cache first
    │  - Batch embed chunks (local model or API)
    │  - Store embeddings in cache
    │
    ▼
Vector Store Upsert
    │  - Store: embedding + chunk text + metadata
    │  - Metadata: doc_id, chunk_index, page_number, source_file, timestamp
    │
    ▼
Index Confirmation → Update UI status
```

### Chunking Configuration (Tunable)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `chunk_size` | 1000 characters | Target chunk size |
| `chunk_overlap` | 200 characters | Overlap between consecutive chunks |
| `chunking_strategy` | `recursive` | Options: `recursive`, `semantic`, `fixed` |
| `respect_boundaries` | `true` | Avoid splitting mid-sentence or mid-paragraph |
| `max_chunks_per_doc` | 5000 | Safety limit to prevent runaway indexing |

---

## 11. RAG Pipeline Design

```
User Query
    │
    ▼
┌──────────────────────────┐
│  Cache Lookup             │
│  1. Exact-match cache     │──── HIT ──→ Return cached response
│  2. Semantic cache        │──── HIT ──→ Return cached response
└──────────┬───────────────┘
           │ MISS
           ▼
Query Preprocessing
    │  - Spell correction
    │  - Query expansion / rewriting (optional LLM call)
    │  - Intent classification
    │
    ▼
Retrieval (Hybrid Search)
    │  ┌─────────────────────┐
    │  │ Dense Retrieval      │  Embedding similarity (cosine)
    │  │ (Vector Search)      │  Top-K = 20
    │  └─────────┬───────────┘
    │            │
    │  ┌─────────▼───────────┐
    │  │ Sparse Retrieval     │  BM25 keyword matching
    │  │ (Optional)           │  Top-K = 20
    │  └─────────┬───────────┘
    │            │
    │  ┌─────────▼───────────┐
    │  │ Reciprocal Rank      │  Merge dense + sparse results
    │  │ Fusion (RRF)         │  Re-rank to Top-K = 5-10
    │  └─────────┬───────────┘
    │
    ▼
Context Assembly
    │  - Deduplicate overlapping chunks
    │  - Order by relevance score
    │  - Trim to fit model context window
    │  - Attach source metadata
    │
    ▼
Prompt Construction
    │  - System prompt: role, constraints, citation format
    │  - Retrieved context (numbered sources)
    │  - Conversation history (if multi-turn)
    │  - User query
    │
    ▼
LLM Generation (via OpenRouter)
    │  - Stream response tokens
    │  - Parse citations from response
    │  - Compute confidence score
    │
    ▼
Post-Processing
    │  - Validate citations against retrieved sources
    │  - Format response with source links
    │  - Log: query, context, response, tokens, latency, model
    │
    ▼
Cache Store
    │  - Store in exact-match cache (query hash → response)
    │  - Store in semantic cache (query embedding → response)
    │
    ▼
Return Response to UI
```

### Retrieval Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `top_k_retrieval` | 20 | Candidates retrieved from vector store |
| `top_k_rerank` | 5 | Final chunks sent to LLM after re-ranking |
| `similarity_threshold` | 0.7 | Minimum cosine similarity to include a chunk |
| `hybrid_search` | `true` | Combine dense + sparse retrieval |
| `reranker_model` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Cross-encoder for re-ranking |

---

## 12. Caching Strategy

IntelRAG implements a **three-tier caching architecture** designed to minimize redundant computation and API costs.

### Tier 1: Exact-Match Response Cache

| Aspect | Detail |
|--------|--------|
| **Key** | SHA-256 hash of `(query_text + document_set_hash + model_id)` |
| **Value** | Full response JSON (answer, sources, metadata) |
| **Store** | Redis (with TTL) |
| **TTL** | Configurable; default 24 hours |
| **Invalidation** | On document add/delete/modify → invalidate all keys for affected document set |
| **Hit Criteria** | Exact query string match against same document corpus and model |

### Tier 2: Semantic Response Cache

| Aspect | Detail |
|--------|--------|
| **Key** | Query embedding vector |
| **Value** | Cached response from a semantically similar prior query |
| **Store** | Redis + vector similarity index (or dedicated semantic cache like GPTCache) |
| **Similarity Threshold** | Configurable; default cosine similarity >= 0.95 |
| **TTL** | Configurable; default 48 hours |
| **Invalidation** | Same as Tier 1 plus periodic pruning of low-hit entries |
| **Hit Criteria** | New query embedding is >= threshold similar to a cached query embedding |

### Tier 3: Embedding Cache

| Aspect | Detail |
|--------|--------|
| **Key** | SHA-256 hash of chunk text |
| **Value** | Embedding vector |
| **Store** | Redis or local LRU cache |
| **TTL** | Indefinite (embeddings are deterministic for same model) |
| **Invalidation** | On embedding model change → full flush |
| **Purpose** | Avoid recomputing embeddings during re-indexing or duplicate uploads |

### Cache Flow Priority

```
Query arrives
    → Check Tier 1 (exact match)  → HIT → return immediately (~5ms)
    → Check Tier 2 (semantic)     → HIT → return immediately (~50ms)
    → MISS → full RAG pipeline    → store result in Tier 1 + Tier 2
```

### Cache Metrics (Admin Dashboard)

- Hit rate per tier (hourly, daily, monthly)
- Estimated cost savings (tokens saved x model pricing)
- Cache size and eviction rate
- Average latency per tier

---

## 13. OpenRouter AI Gateway Integration

### Why OpenRouter

| Benefit | Detail |
|---------|--------|
| **Single API** | One API key to access 100+ models from OpenAI, Anthropic, Google, Meta, Mistral, etc. |
| **Cost Routing** | Automatically route to cheaper models for simple queries |
| **Fallback** | Built-in model fallback if primary model is unavailable |
| **Usage Tracking** | Per-request cost and token tracking via API response headers |
| **OpenAI-Compatible** | Drop-in replacement using the `openai` Python SDK |

### Integration Design

```python
# Simplified OpenRouter client configuration
import openai

client = openai.OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
    default_headers={
        "HTTP-Referer": "https://intelrag.example.com",
        "X-Title": "IntelRAG",
    },
)
```

### Model Tier Strategy

IntelRAG routes every query to one of three model tiers based on detected complexity. All models are accessed through OpenRouter's unified API.

| Tier | Complexity | Provider | Models (via OpenRouter) | Est. Cost (per 1M tokens) |
|------|-----------|----------|------------------------|--------------------------|
| **Tier 1 — Free** | Simple | OpenRouter Free Models | `meta-llama/llama-3.1-8b-instruct:free`, `mistralai/mistral-7b-instruct:free`, `google/gemma-2-9b-it:free` | **$0.00** (free tier) |
| **Tier 2 — Gemini** | Moderate | Google (via OpenRouter) | `google/gemini-2.0-flash`, `google/gemini-2.0-pro` | $0.10 – $1.25 |
| **Tier 3 — OpenAI** | Complex | OpenAI (via OpenRouter) | `openai/gpt-4o`, `openai/gpt-4o-mini` | $2.50 – $10.00 |

### Fallback Chain

If the selected tier's model is unavailable (rate-limited, down, or erroring), the system automatically escalates:

```
Tier 1 (Free) ──fail──▶ Tier 2 (Gemini) ──fail──▶ Tier 3 (OpenAI)
```

Fallback events are logged and surfaced on the admin dashboard so cost impact is visible.

### Intelligent Model Routing (Core Feature)

Every incoming query passes through a **Query Complexity Classifier** before reaching any LLM. This classifier must add < 100ms of latency.

#### Classification Criteria

| Complexity | Characteristics | Examples | Routed To |
|-----------|----------------|----------|-----------|
| **Simple** | Single fact, short answer expected, keyword-like, single-document lookup, definition requests | "What is the project deadline?", "Define SLA.", "Who is the author of document X?" | **Tier 1 — OpenRouter Free** |
| **Moderate** | Paragraph-level answer, summarization, single-document reasoning, comparison of 2 items, general Q&A | "Summarize the key findings of the Q3 report.", "What are the main risks listed in the RFP?" | **Tier 2 — Gemini** |
| **Complex** | Multi-document synthesis, multi-step reasoning, comparative analysis across many docs, strategic recommendations, long-form generation | "Compare the pricing models across all three vendor proposals and recommend the best option.", "What contradictions exist between the legal opinion and the compliance report?" | **Tier 3 — OpenAI** |

#### Classifier Implementation

The classifier uses a **hybrid approach** for accuracy and speed:

1. **Rule-Based Layer (primary, ~5ms)**
   - Query length: short (< 15 tokens) → leans Simple
   - Question type: "what is", "who", "when" → leans Simple; "compare", "analyze", "synthesize" → leans Complex
   - Keyword signals: "summarize", "list" → Moderate; "recommend", "evaluate", "contrast" → Complex
   - Number of relevant documents retrieved: 1 doc → Simple/Moderate; 3+ docs → Complex
   - Conversation depth: first message → use rules; 3+ turns deep → escalate to Moderate/Complex

2. **Embedding-Based Refinement (optional, ~50ms)**
   - Cluster historical queries by complexity using labeled examples
   - Classify new queries by nearest-cluster assignment
   - Improves over time as more labeled data accumulates via the feedback loop

3. **Admin Override**
   - Force a specific tier for all queries (useful for demos, testing, or budget constraints)
   - Set a "max tier" ceiling (e.g., never use Tier 3 to cap costs)

#### Cost Impact Visualization

```
Query Volume Distribution (target):          Estimated Monthly Cost (50K queries):

  Simple  ████████████████████  60%           Tier 1 (Free):   $0.00
  Moderate ██████████  30%                    Tier 2 (Gemini): $15 – $40
  Complex  ████  10%                          Tier 3 (OpenAI): $25 – $100
                                              ─────────────────────────
                                              Total:           $40 – $140
```

By routing 60% of queries to free models and only 10% to OpenAI, the system keeps costs at a fraction of what an all-OpenAI deployment would cost (~$500–$1,000/month for the same volume).

---

## 14. Streamlit UI Specification

### Page Layout

The application uses a **multi-page Streamlit app** with sidebar navigation.

### Pages

#### Page 1: Document Manager

| Element | Description |
|---------|-------------|
| **File Uploader** | `st.file_uploader` with `accept_multiple_files=True`; supports all listed file types |
| **Upload Progress** | Per-file progress bars with status badges (queued / processing / indexed / failed) |
| **Document Table** | Sortable, filterable table of all indexed documents with columns: Name, Type, Size, Pages, Chunks, Upload Date, Status |
| **Actions** | Delete document (with confirmation), re-index, download original |
| **Bulk Upload** | ZIP upload option for batch processing |
| **Storage Indicator** | Total documents, total chunks, vector store size |

#### Page 2: Chat Interface

| Element | Description |
|---------|-------------|
| **Chat Container** | `st.chat_message` components for conversation display |
| **Input** | `st.chat_input` with placeholder text |
| **Source Panel** | Expandable sidebar or accordion showing retrieved sources with highlights |
| **Cache Indicator** | Badge showing if response was served from cache (and which tier) |
| **Model Selector** | Dropdown to override the default model (power user feature) |
| **Streaming** | Token-by-token response rendering |
| **Conversation Controls** | New conversation, export chat, clear history |
| **Confidence Badge** | Color-coded confidence level per response |

#### Page 3: Admin Dashboard

| Element | Description |
|---------|-------------|
| **Usage Metrics** | Total queries, tokens consumed, estimated cost (today / this week / this month) |
| **Cache Performance** | Hit rate charts per tier, cost savings estimate |
| **Document Stats** | Total documents, chunks, storage used |
| **Query Log** | Searchable table of recent queries with details |
| **System Config** | Model selection, cache TTL, chunk size, similarity thresholds |
| **Health Status** | Vector store, Redis, OpenRouter API connectivity indicators |

### UI/UX Guidelines

- Use `st.set_page_config(layout="wide")` for maximum content area
- Apply custom CSS via `st.markdown` for professional styling
- Implement dark/light theme toggle
- Show loading spinners during processing with informative messages
- Use `st.toast` for non-blocking notifications
- Responsive design considerations for tablet-width viewports

---

## 15. Enterprise Best Practices

### 14.1 Code Quality & Development

| Practice | Implementation |
|----------|---------------|
| Type hints everywhere | `mypy --strict` in CI |
| Linting | `ruff` with strict configuration |
| Testing | `pytest` with >= 80% coverage enforced |
| Dependency management | `poetry` or `uv` with lockfile |
| Pre-commit hooks | ruff, mypy, pytest (fast subset) |
| Documentation | Docstrings (Google style), architecture decision records (ADRs) |

### 14.2 Configuration Management

- All secrets via environment variables (never in code)
- Use `pydantic-settings` for typed, validated configuration
- Separate config profiles: `development`, `staging`, `production`
- Feature flags for gradual rollout of new capabilities

### 14.3 Error Handling & Resilience

| Pattern | Application |
|---------|-------------|
| **Circuit Breaker** | On OpenRouter API calls — trip after N failures, fallback to cache |
| **Retry with Backoff** | Exponential backoff on transient API errors (429, 503) |
| **Graceful Degradation** | If vector store is down, inform user; if LLM is down, serve cache only |
| **Dead Letter Queue** | Failed document ingestions queued for retry |
| **Timeout Management** | Per-operation timeouts (embedding: 30s, LLM: 60s, ingestion: 300s) |

### 14.4 Observability

| Layer | Tool | Purpose |
|-------|------|---------|
| **Logging** | `structlog` | JSON structured logs, correlation IDs per request |
| **Metrics** | `prometheus_client` | Cache hit rates, latency histograms, token counts |
| **Tracing** | OpenTelemetry | End-to-end request traces across ingestion and query paths |
| **Alerting** | Prometheus Alertmanager / PagerDuty | Cost budget thresholds, error rate spikes, latency degradation |

### 14.5 Data Governance

- Document-level access control (future: RBAC per collection)
- Query audit trail with immutable log
- Data retention policy: configurable auto-purge of old documents and cache
- PII detection and redaction pipeline (enhancement)

---

## 16. Cost Optimization Strategy

### 15.1 Cost Breakdown Model

| Cost Component | Driver | Optimization Lever |
|----------------|--------|-------------------|
| **LLM API calls** | Tokens consumed per query | Caching, model tiering, context trimming |
| **Embedding API** | Tokens embedded | Local embedding model, embedding cache |
| **Vector store** | Storage + queries | Efficient chunking, deduplication, managed vs. self-hosted |
| **Infrastructure** | Compute + memory | Right-sizing containers, auto-scaling |
| **Redis** | Memory | TTL policies, eviction strategies, memory-efficient data structures |

### 15.2 Cost Reduction Tactics

| Tactic | Expected Savings | Implementation |
|--------|-----------------|----------------|
| **Complexity-based routing** | 70-85% vs. all-OpenAI | Route 60% of queries to free models (Tier 1), 30% to Gemini (Tier 2), only 10% to OpenAI (Tier 3) |
| **Semantic caching** | 40-60% of remaining LLM costs | Semantic cache with 0.95 similarity threshold |
| **Local embeddings** | 100% of embedding API costs | `all-MiniLM-L6-v2` or `bge-small-en-v1.5` locally |
| **Context window optimization** | 20-30% of per-query cost | Re-rank and trim to only the most relevant chunks |
| **Batch embedding** | 15-20% latency savings | Process chunks in batches of 64-128 |
| **Deduplication** | Variable | Skip re-indexing identical documents |
| **OpenRouter free tier maximization** | 60% of queries at $0 | Maintain a rotation of free models to stay within rate limits |

### 15.3 Monthly Cost Estimate (Reference)

**With complexity-based routing (Free → Gemini → OpenAI):**

| Scenario | Queries/Month | Tier 1 (Free) | Tier 2 (Gemini) | Tier 3 (OpenAI) | Cache Savings | **Est. Total** |
|----------|--------------|---------------|-----------------|-----------------|--------------|----------------|
| **Small Team** (5 users, 500 docs) | 5,000 | $0 | $3 – $8 | $5 – $20 | ~40% | **$5 – $17** |
| **Department** (50 users, 5,000 docs) | 50,000 | $0 | $15 – $40 | $25 – $100 | ~50% | **$20 – $70** |
| **Enterprise** (500 users, 50,000 docs) | 500,000 | $0 | $80 – $250 | $150 – $600 | ~60% | **$90 – $340** |

*Assumes 60/30/10 query distribution across tiers, local embeddings, self-hosted vector store, and cache hit rates scaling with user volume.*

**Comparison with single-model approaches:**

| Strategy | 50K Queries/Month | Savings vs. All-OpenAI |
|----------|-------------------|----------------------|
| All OpenAI (GPT-4o) | $500 – $1,000 | — |
| All Gemini (2.0 Flash) | $50 – $125 | 87% |
| **IntelRAG Tiered (Free + Gemini + OpenAI)** | **$20 – $70** | **93%** |

### 15.4 Cost Monitoring

- Real-time cost dashboard in admin panel
- Per-user and per-department cost attribution
- Budget alerts at 50%, 80%, 100% thresholds
- Weekly cost report emails to admins

---

## 17. Security & Compliance

### 16.1 Application Security

| Control | Implementation |
|---------|---------------|
| **Authentication** | Streamlit session auth or LDAP/SSO integration (enterprise) |
| **Authorization** | Role-based: Admin, Power User, Standard User |
| **Input Sanitization** | Validate all file uploads (type, size, content); sanitize query inputs |
| **Data Encryption** | TLS in transit; AES-256 at rest for document store |
| **API Key Security** | OpenRouter key stored in env var / secret manager; never logged |
| **Rate Limiting** | Per-user query rate limits to prevent abuse |
| **CORS** | Restrict to known origins in production |

### 16.2 Data Privacy

| Concern | Mitigation |
|---------|-----------|
| **Document confidentiality** | Documents processed and stored locally; optional on-prem deployment |
| **LLM data leakage** | Use OpenRouter's data privacy options; avoid sending full documents to LLM |
| **PII in queries** | Optional PII detection and masking before LLM call |
| **Audit trail** | Immutable query logs for compliance review |
| **Data residency** | Configurable vector store location; support for EU/US regions |

### 16.3 Compliance Alignment

- SOC 2 Type II alignment (access controls, audit logging, encryption)
- GDPR considerations (right to deletion, data portability)
- HIPAA considerations (if healthcare documents — requires additional controls)

---

## 18. Proposed Enhancements

These are gaps identified in the original requirements and recommended additions for a production-grade system.

### Enhancement 1: Multi-Collection Support

Allow users to create named document collections (e.g., "Legal Contracts", "Engineering Docs") and query within or across collections. This improves retrieval precision and enables access control per collection.

### Enhancement 2: Agentic RAG

Extend beyond simple retrieve-and-generate:
- **Multi-step reasoning**: Break complex queries into sub-queries, retrieve for each, synthesize
- **Tool use**: Allow the LLM to call tools (calculator, date parser, web search) when document context is insufficient
- **Self-reflection**: LLM evaluates its own answer quality and retries if confidence is low

### Enhancement 3: Feedback Loop & Active Learning

- Thumbs up/down on responses
- Explicit correction mechanism ("the answer should be...")
- Use feedback data to fine-tune retrieval (re-rank model) and cache prioritization
- Periodic evaluation against a golden QA dataset

### Enhancement 4: Scheduled Ingestion

- Watch folders or cloud storage (S3, GCS, SharePoint) for new documents
- Automatic re-indexing on document changes
- Webhook support for integration with document management systems

### Enhancement 5: Advanced Analytics

- Topic clustering across the document corpus
- Question trend analysis (what are users asking about most?)
- Knowledge gap detection (questions with low-confidence answers)
- Document coverage analysis (which docs are never retrieved?)

### Enhancement 6: Multi-Modal RAG

- Support for images within documents (charts, diagrams) using vision models
- Audio/video transcription and indexing (Whisper integration)
- Table extraction with structure preservation

### Enhancement 7: Collaborative Features

- Shared conversations with team members
- Pinned/bookmarked answers
- Annotation on documents (highlight + comment)

### Enhancement 8: Local / Offline Mode

- Support for fully local LLM execution via `ollama` or `vLLM` as an alternative to OpenRouter
- Useful for air-gapped or highly sensitive environments
- Configurable toggle between local and cloud LLM

---

## 19. Milestones & Roadmap

### Phase 1: Foundation (Weeks 1–3)

| Milestone | Deliverable |
|-----------|------------|
| M1.1 | Project scaffolding, dependency setup, Docker config |
| M1.2 | Document parsers for PDF, DOCX, TXT, CSV, MD |
| M1.3 | Chunking pipeline with configurable strategy |
| M1.4 | Embedding generation (local model) + ChromaDB integration |
| M1.5 | Basic Streamlit UI: upload + simple query |

### Phase 2: Core RAG (Weeks 4–6)

| Milestone | Deliverable |
|-----------|------------|
| M2.1 | OpenRouter integration with streaming |
| M2.2 | Full RAG pipeline: retrieve → re-rank → generate |
| M2.3 | Source citation in responses |
| M2.4 | Multi-turn conversation support |
| M2.5 | Confidence scoring |

### Phase 3: Enterprise Caching (Weeks 7–9)

| Milestone | Deliverable |
|-----------|------------|
| M3.1 | Redis deployment + exact-match cache |
| M3.2 | Semantic cache implementation |
| M3.3 | Embedding cache |
| M3.4 | Cache invalidation logic |
| M3.5 | Cache metrics dashboard |

### Phase 4: Polish & Production (Weeks 10–12)

| Milestone | Deliverable |
|-----------|------------|
| M4.1 | Admin dashboard (full) |
| M4.2 | Model tiering and intelligent routing |
| M4.3 | Structured logging + OpenTelemetry tracing |
| M4.4 | Security hardening (auth, rate limiting, input validation) |
| M4.5 | Load testing, performance tuning, documentation |
| M4.6 | CI/CD pipeline, Docker Compose production config |

### Phase 5: Enhancements (Weeks 13+)

- Multi-collection support
- Agentic RAG
- Feedback loop
- Scheduled ingestion
- Multi-modal support

---

## 20. Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|-----------|
| R1 | OpenRouter API outage | Medium | High | Multi-tier cache serves existing answers; local LLM fallback (Phase 5) |
| R2 | Poor retrieval quality on domain-specific docs | Medium | High | Fine-tune embedding model; hybrid search; user feedback loop |
| R3 | Cost overrun from LLM API usage | Medium | Medium | Aggressive caching; model tiering; budget alerts and hard limits |
| R4 | Streamlit scaling limitations for large teams | Low | Medium | Evaluate migration to FastAPI + React if needed (future phase) |
| R5 | Vector store performance at scale | Low | High | Benchmark ChromaDB vs. Qdrant early; plan migration path |
| R6 | Data privacy concerns with cloud LLM | Medium | High | On-prem / local LLM option; PII detection; data processing agreements |
| R7 | Document parser failures on edge cases | High | Low | Comprehensive error handling; fallback to raw text extraction; user notification |
| R8 | Cache staleness (outdated answers) | Medium | Medium | Aggressive invalidation on doc changes; configurable TTL; manual purge |

---

## 21. Glossary

| Term | Definition |
|------|-----------|
| **RAG** | Retrieval-Augmented Generation — a pattern where relevant documents are retrieved and provided as context to an LLM to generate grounded answers |
| **Embedding** | A dense vector representation of text that captures semantic meaning, used for similarity search |
| **Vector Store** | A database optimized for storing and querying high-dimensional embedding vectors |
| **Chunking** | The process of splitting documents into smaller, overlapping segments for embedding and retrieval |
| **Semantic Cache** | A cache layer that matches queries based on meaning similarity rather than exact string match |
| **OpenRouter** | An AI gateway service that provides a unified API to access multiple LLM providers |
| **Re-ranking** | A second-stage retrieval step that uses a cross-encoder model to score and re-order candidate chunks |
| **Hybrid Search** | Combining dense (embedding) and sparse (keyword/BM25) retrieval for improved recall |
| **RRF** | Reciprocal Rank Fusion — a method for merging ranked lists from different retrieval strategies |
| **TTL** | Time-To-Live — the duration a cached entry remains valid before expiration |
| **Circuit Breaker** | A resilience pattern that stops calling a failing service after repeated failures, allowing recovery time |
| **RAGAS** | A framework for evaluating RAG pipeline quality (Retrieval Augmented Generation Assessment) |

---

*End of PRD — IntelRAG v1.0*
