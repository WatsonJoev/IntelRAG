# IntelRAG — Security Review

**Date:** 2026-07-05
**Scope:** Full application — Streamlit UI (`app/`), FastAPI v2 UI (`web/`), core RAG pipeline (`core/`), ingestion (`ingestion/`), data layer (`models/`), configuration (`config/`), Docker/compose infrastructure.
**Verdict:** Solid single-user development platform with good engineering hygiene, but **not yet enterprise-ready**. The blocking gaps are authentication/authorization, tenancy, stored XSS in the Streamlit document list, missing CSRF protection, and unenforced upload/rate limits on the FastAPI surface.

---

## High severity

### H1. No authentication or authorization on any surface
Every endpoint is anonymous: chat, document upload, document **delete**, the admin dashboard (which exposes every user's query text, costs, and system health), `/healthz`, and the auto-generated OpenAPI docs at `/docs`. `user_id` is hardcoded (`"local"` in `web/server.py:118`, `"default"` in `models/db.py:66`). Anyone with network access can read the whole knowledge base through chat, delete all documents, and read the full query audit log.

**Fix:** Put an identity layer in front of both UIs (OIDC/SAML via a reverse proxy such as oauth2-proxy, or FastAPI middleware with your IdP). Gate `/v2/admin`, `/docs`, and `/healthz` behind an admin role. Propagate the real user identity into `Conversation.user_id` and `QueryLog.session_id`.

### H2. Stored XSS via uploaded filename (Streamlit document list)
`app/views/documents.py:219-225` interpolates the raw uploaded filename into `st.markdown(f"...{d.filename}...", unsafe_allow_html=True)`. A file named `<img src=x onerror=...>.pdf` executes script in the browser of anyone who opens the Documents page. (`FileStore._sanitize_filename` protects the *disk path*, but the *original* filename is stored in the DB and rendered raw.)

**Fix:** HTML-escape the filename (`html.escape(d.filename)`) before interpolation — same for the `title` attribute — or render the row without `unsafe_allow_html`.

### H3. No CSRF protection on state-changing FastAPI endpoints
`POST /v2/api/ingest`, `POST /v2/api/documents/{doc_id}/delete`, and `POST /v2/api/chat` accept form posts with no CSRF token. `SameSite=lax` on the session cookie does not stop cross-site *top-level form POSTs* to unauthenticated endpoints — a malicious page can delete documents in one request.

**Fix:** Add CSRF tokens (e.g. `starlette-csrf` or double-submit cookie validated in middleware) once auth exists; until then this is subsumed by H1.

### H4. Unbounded upload on FastAPI ingest — memory-exhaustion DoS
`web/server.py:212` does `await file.read()` with **no size check**. `MAX_FILE_SIZE_MB` (200 MB) is enforced only in the Streamlit view (`app/views/documents.py:114-146`). A single multi-GB POST to `/v2/api/ingest` is read fully into memory. There is also no request-body limit at the ASGI layer.

**Fix:** Check `file.size` / stream to disk with a byte cap in the ingest endpoint; set a body-size limit at the reverse proxy.

### H5. Rate limiting is configured but never enforced
`QUERY_RATE_LIMIT_PER_USER=100` exists in settings/.env.example but is referenced nowhere in the code. Each chat request triggers embedding + up to three paid LLM calls (fallback chain) — an unauthenticated attacker can run up unbounded OpenRouter spend.

**Fix:** Enforce per-session/per-IP rate limiting (e.g. `slowapi` for FastAPI; middleware or reverse-proxy limits for Streamlit). Add a daily cost circuit-breaker using the existing `TokenUsage` table.

---

## Medium severity

### M1. Incomplete, inconsistent deletion (data-retention / right-to-erasure failure)
- **Streamlit delete** (`app/views/documents.py:227-235`): deletes raw files and marks `status="deleted"` — but **never removes vectors from ChromaDB**, so deleted document content remains retrievable in chat.
- **FastAPI delete** (`web/server.py:223-236`): deletes the DB row and vectors — but **never deletes the raw file** from the file store, and does not call `cache_mgr.invalidate_on_doc_change()`.

**Fix:** One shared `delete_document()` service in `core/` that removes DB rows, vectors, raw files, and invalidates cache — used by both UIs.

### M2. Session cookie weaknesses (conversation IDOR)
The `sid` cookie (`web/server.py:88-126`) is unsigned, has no `Secure` flag, no `max_age`/rotation, and any presented value is trusted — whoever holds (or intercepts, over plain HTTP) a `sid` reads that conversation history. UUID4 is not guessable, but the cookie is the *only* access control.

**Fix:** `secure=True` behind TLS, signed sessions (itsdangerous / starlette SessionMiddleware), and bind conversations to the authenticated user once H1 is fixed.

### M3. Internal error details leaked to the browser
`web/server.py:190-194` renders `f"Unexpected error: {e}"` to the client — exception text can reveal paths, connection strings, or stack context.

**Fix:** Log the exception (already done), return a generic message with a correlation ID.

### M4. Indirect prompt injection — untrusted documents in the system role
`core/prompt_builder.py:30` places raw document text into a **system** message. A malicious uploaded document can instruct the model ("ignore previous instructions…"). No spotlighting/delimiting or output filtering exists. Impact today is answer manipulation and fabricated citations (link rendering is XSS-safe); severity grows if tool use is added later.

**Fix:** Move context to a `user`-role message wrapped in clear delimiters with an instruction that the content is untrusted data; consider a citation-consistency check.

### M5. Container and compose hardening
- `Dockerfile` runs as **root** (no `USER` directive) and ships `build-essential` in the final image (no multi-stage build).
- `docker-compose.yml` publishes **Redis (6379 + RedisInsight 8001), Qdrant (6333), and Postgres (5432) to the host** with no auth (`--requirepass` absent; `QDRANT_API_KEY` empty) and a default Postgres password fallback (`intelrag`).
- The `full` profile claims PostgreSQL in the docs but pins `DATABASE_URL=sqlite://...` (config drift).

**Fix:** Non-root `USER`, multi-stage build, bind service ports to an internal network only, require passwords, align `full` profile to Postgres.

### M6. No security headers / CSP; CDN scripts without SRI
The v2 UI loads Tailwind and htmx from CDNs (`web/templates/base.html:8-9`) with no `integrity` attribute, and no CSP, `X-Frame-Options`, or HSTS headers anywhere. A CDN compromise becomes full script execution in the app.

**Fix:** Pin htmx with an SRI hash (the Tailwind Play CDN cannot use SRI — replace with a built CSS file for production), add a security-headers middleware.

---

## Low severity

- **L1.** `echo=settings.environment == "development"` (`models/session.py:20`) logs every SQL statement — including query text and conversation content (potential PII) — to stdout in dev.
- **L2.** `Document.file_store_path` is recorded as `f"{doc_id}/{Path(filename).name}"` (`ingestion/pipeline.py:58`) but the file is saved under the *sanitized* name — the DB path can point at a nonexistent file.
- **L3.** `OPENROUTER_API_KEY` defaults to `""` and startup proceeds silently; failures surface late as LLM errors. Fail fast in `staging`/`production` profiles.
- **L4.** `/healthz` publicly reveals which backend components are up (minor recon value; gate with H1).
- **L5.** Duplicate-check response (`"duplicate"`, returning the existing doc id) lets any uploader confirm whether a given file already exists in the corpus (content-existence oracle) — acceptable single-tenant, revisit with multi-tenancy.

---

## What is already done well

- **No raw SQL anywhere** — all DB access via SQLAlchemy ORM with bound parameters (no SQL injection surface found).
- **XSS-safe LLM output in v2** — markdown rendered with `html=False` so raw HTML from the model is escaped; Jinja autoescaping on for all `.html` templates.
- **Server-generated document IDs** (UUID) — no user-controlled path components reach `FileStore`; filenames are sanitized before hitting disk.
- **Secrets hygiene** — `.env` gitignored and untracked; secrets only via environment; no credentials committed.
- **Resilience** — LLM retry with exponential backoff + jitter, tier fallback chain, ingestion failures isolated per document.
- **Auditability** — structured JSON logs, per-query `QueryLog` (model, tokens, cost, latency, cache tier), `IngestionLog`, daily `TokenUsage` rollups.
- **SHA-256 duplicate detection** and content hashing at ingest.
- **Pinned infrastructure images** in compose (redis-stack 7.2.0-v6, qdrant v1.9.0, postgres 16-alpine).

---

## Enterprise-readiness checklist (priority order)

| # | Item | Status |
|---|------|--------|
| 1 | Authentication + RBAC (users, admin role) | ❌ Missing |
| 2 | Fix stored XSS in Streamlit document list | ❌ Missing |
| 3 | Enforce upload size + rate limits on FastAPI surface | ❌ Missing |
| 4 | CSRF protection on state-changing endpoints | ❌ Missing |
| 5 | Unified complete deletion (DB + vectors + files + cache) | ❌ Missing |
| 6 | TLS termination + secure/signed session cookies | ❌ Missing |
| 7 | Non-root container, internal-only service ports, DB/Redis/Qdrant auth | ❌ Missing |
| 8 | Security headers + SRI/pinned assets (drop Tailwind Play CDN) | ❌ Missing |
| 9 | Prompt-injection guardrails (untrusted-context framing) | ❌ Missing |
| 10 | Cost circuit-breaker on daily LLM spend | ❌ Missing |
| 11 | Generic error responses with correlation IDs | ❌ Missing |
| 12 | Multi-tenancy (per-user document scoping) | ❌ Missing (single-tenant by design today) |
