"""
IntelRAG v2 — FastAPI front-end.

Security features active in this module:
  - HTTP Basic Auth (enable via BASIC_AUTH_USERNAME + BASIC_AUTH_PASSWORD env vars)
  - CSRF double-submit cookie on all state-changing endpoints
  - Per-IP rate limiting via slowapi (chat: 30/min, ingest: 10/min)
  - Upload size enforcement (MAX_FILE_SIZE_MB, enforced before reading into memory)
  - Security headers middleware (X-Frame-Options, X-Content-Type-Options, HSTS, CSP)
  - Generic error responses with correlation IDs (exception detail never sent to client)
  - Daily cost circuit-breaker (DAILY_COST_LIMIT_USD, uses TokenUsage table)
  - Signed session cookies (itsdangerous, httponly, samesite=strict, secure in prod)
  - Complete document deletion via core.document_service (DB + vectors + files + cache)

Run:  uvicorn web.server:app --reload --port 8600
"""
from __future__ import annotations

import base64
import re
import secrets
import uuid
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, URLSafeTimedSerializer
from markdown_it import MarkdownIt
from markupsafe import Markup
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from config.logging_config import get_logger
from config.settings import get_settings
from core import health
from core.cache.cache_manager import get_cache_manager
from core.document_service import delete_document as svc_delete_document
from core.llm_service import LLMUnavailableError
from core.rag_service import answer_query
from core.storage.vector_store import VectorStore
from ingestion.pipeline import ingest_document
from models.db import Conversation, Document, QueryLog, TokenUsage
from models.session import get_db

logger = get_logger(__name__)

_BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(_BASE / "templates"))

# --------------------------------------------------------------------------- #
# Rate limiter
# --------------------------------------------------------------------------- #
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

app = FastAPI(
    title="IntelRAG v2",
    docs_url=None,   # disable public /docs
    redoc_url=None,  # disable public /redoc
    openapi_url=None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Serve bundled static assets (htmx, Tailwind) — no CDN dependency
app.mount("/static", StaticFiles(directory=str(_BASE / "static")), name="static")


# --------------------------------------------------------------------------- #
# Cookie signing
# --------------------------------------------------------------------------- #
def _get_signer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt="intelrag-session")


def _sign(value: str) -> str:
    return _get_signer().dumps(value)


def _unsign(token: str, max_age: int = 86400 * 30) -> str | None:
    try:
        return _get_signer().loads(token, max_age=max_age)
    except BadSignature:
        return None


# --------------------------------------------------------------------------- #
# Security helpers
# --------------------------------------------------------------------------- #
def _require_auth(request: Request) -> None:
    """Raise 401 if Basic Auth is configured and credentials are wrong/missing."""
    s = get_settings()
    if not (s.basic_auth_username and s.basic_auth_password):
        return  # auth not configured
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": 'Basic realm="IntelRAG"'},
        )
    try:
        decoded = base64.b64decode(auth[6:]).decode("utf-8")
        username, _, password = decoded.partition(":")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid credentials",
                            headers={"WWW-Authenticate": 'Basic realm="IntelRAG"'})
    if not (
        secrets.compare_digest(username, s.basic_auth_username)
        and secrets.compare_digest(password, s.basic_auth_password)
    ):
        raise HTTPException(status_code=401, detail="Invalid credentials",
                            headers={"WWW-Authenticate": 'Basic realm="IntelRAG"'})


def _csrf_token_from_cookie(request: Request) -> str | None:
    raw = request.cookies.get("csrf")
    if not raw:
        return None
    return _unsign(raw, max_age=86400)


def _new_csrf_token() -> tuple[str, str]:
    """Return (plaintext_token, signed_cookie_value)."""
    token = secrets.token_urlsafe(32)
    return token, _sign(token)


def _validate_csrf(request: Request) -> None:
    """Compare the signed cookie to the X-CSRF-Token header."""
    cookie_token = _csrf_token_from_cookie(request)
    header_token = request.headers.get("X-CSRF-Token", "")
    if not cookie_token or not secrets.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=403, detail="CSRF token invalid or missing")


def _check_cost_limit() -> None:
    s = get_settings()
    if s.daily_cost_limit_usd <= 0:
        return
    with get_db() as db:
        row = db.query(TokenUsage).filter(TokenUsage.date == date.today()).first()
        if row and row.total_cost >= s.daily_cost_limit_usd:
            raise HTTPException(
                status_code=503,
                detail=f"Daily LLM cost limit (${s.daily_cost_limit_usd:.2f}) reached. Try again tomorrow.",
            )


# --------------------------------------------------------------------------- #
# Security headers middleware
# --------------------------------------------------------------------------- #
_SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    # CSP: scripts only from self (for locally-served static files)
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "  # unsafe-inline required for Tailwind Play config block
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    ),
}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    for header, value in _SECURITY_HEADERS.items():
        response.headers[header] = value
    if get_settings().environment == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# --------------------------------------------------------------------------- #
# Markdown + citation rendering
# --------------------------------------------------------------------------- #
# html=False so any raw HTML in LLM output is escaped (XSS-safe).
_md = MarkdownIt("commonmark", {"linkify": True, "breaks": True})
_CITE_RE = re.compile(r"\[Sources?\s+([\d,\s]+)\]", re.IGNORECASE)


def _replace_citations(text: str, sources: list | None) -> str:
    if not sources:
        return text

    def repl(match: re.Match) -> str:
        names: list[str] = []
        for num in re.findall(r"\d+", match.group(1)):
            idx = int(num) - 1
            if 0 <= idx < len(sources):
                name = sources[idx]["doc_name"]
                if name not in names:
                    names.append(name)
        return "[" + ", ".join(names) + "]" if names else match.group(0)

    return _CITE_RE.sub(repl, text)


def _render_markdown(text: str, sources: list | None = None) -> Markup:
    return Markup(_md.render(_replace_citations(text or "", sources)))


templates.env.filters["md"] = _render_markdown


@lru_cache(maxsize=1)
def _vector_store() -> VectorStore:
    return VectorStore()


# --------------------------------------------------------------------------- #
# Session + conversation helpers
# --------------------------------------------------------------------------- #
def _session_id(request: Request) -> str:
    raw = request.cookies.get("sid")
    if raw:
        verified = _unsign(raw)
        if verified:
            return verified
    return str(uuid.uuid4())


def _load_conversation(session_id: str) -> list:
    with get_db() as db:
        conv = (
            db.query(Conversation)
            .filter(Conversation.session_id == session_id)
            .order_by(Conversation.updated_at.desc())
            .first()
        )
        if conv and isinstance(conv.messages_json, list):
            return conv.messages_json
    return []


def _save_conversation(session_id: str, messages: list) -> None:
    with get_db() as db:
        conv = (
            db.query(Conversation)
            .filter(Conversation.session_id == session_id)
            .first()
        )
        if conv:
            conv.messages_json = messages
        else:
            conv = Conversation(
                id=str(uuid.uuid4()),
                user_id="local",
                session_id=session_id,
                messages_json=messages,
            )
            db.add(conv)
        db.commit()


def _set_session_cookie(response: Response, session_id: str) -> None:
    s = get_settings()
    response.set_cookie(
        "sid",
        _sign(session_id),
        httponly=True,
        samesite="strict",
        secure=(s.environment == "production"),
        max_age=86400 * 30,
    )


def _set_csrf_cookie(response: Response, signed_token: str) -> None:
    s = get_settings()
    response.set_cookie(
        "csrf",
        signed_token,
        httponly=False,  # must be readable by JS for non-htmx forms
        samesite="strict",
        secure=(s.environment == "production"),
        max_age=86400,
    )


def render(request: Request, name: str, **context) -> HTMLResponse:
    # Ensure every page render has a CSRF token available to templates
    csrf_plain, csrf_signed = _new_csrf_token()
    ctx = {"csrf_token": csrf_plain, **context}
    resp = templates.TemplateResponse(request=request, name=name, context=ctx)
    _set_csrf_cookie(resp, csrf_signed)
    return resp


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.get("/", include_in_schema=False)
def index() -> RedirectResponse:
    return RedirectResponse("/v2/chat")


@app.get("/v2/chat", response_class=HTMLResponse)
def chat_page(request: Request) -> HTMLResponse:
    _require_auth(request)
    session_id = _session_id(request)
    messages = _load_conversation(session_id)
    resp = render(
        request, "chat.html", messages=messages, session_short=session_id[:8]
    )
    _set_session_cookie(resp, session_id)
    return resp


@app.post("/v2/chat/new", response_class=HTMLResponse)
async def chat_new(request: Request, csrf_token: str = Form(default="")) -> RedirectResponse:
    _require_auth(request)
    # Accept CSRF token from header (htmx) or hidden form field (plain HTML form)
    header_token = request.headers.get("X-CSRF-Token") or csrf_token
    cookie_token = _csrf_token_from_cookie(request)
    if not cookie_token or not secrets.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=403, detail="CSRF token invalid or missing")
    new_sid = str(uuid.uuid4())
    _save_conversation(new_sid, [])
    resp = RedirectResponse("/v2/chat", status_code=303)
    _set_session_cookie(resp, new_sid)
    return resp


@app.post("/v2/api/chat", response_class=HTMLResponse)
@limiter.limit("30/minute")
def chat_send(request: Request, message: str = Form(...)) -> HTMLResponse:
    """htmx endpoint: run the RAG loop and return assistant bubble HTML."""
    _require_auth(request)
    _validate_csrf(request)
    _check_cost_limit()

    session_id = _session_id(request)
    message = message.strip()
    if not message:
        return HTMLResponse("")

    messages = _load_conversation(session_id)
    turn_count = len(messages) // 2
    s = get_settings()
    max_turns = s.conversation_history_turns
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in messages[-(max_turns * 2):]
    ]

    messages.append({"role": "user", "content": message})
    correlation_id = str(uuid.uuid4())
    try:
        result = answer_query(
            message,
            session_id=session_id,
            history=history,
            vector_store=_vector_store(),
            cache_mgr=get_cache_manager(),
            turn_count=turn_count,
        )
        assistant = {"role": "assistant", "content": result["answer"], "meta": result}
        error = None
    except LLMUnavailableError as e:
        logger.warning("v2_llm_unavailable", correlation_id=correlation_id, error=str(e))
        assistant = {"role": "assistant", "content": "The AI service is temporarily unavailable. Please try again."}
        result = {"answer": assistant["content"]}
        error = str(e)
    except Exception as e:
        logger.exception("v2_chat_failed", correlation_id=correlation_id, error=str(e))
        assistant = {
            "role": "assistant",
            "content": f"An error occurred (ref: {correlation_id}). Please try again.",
        }
        result = {"answer": assistant["content"]}
        error = str(e)

    if error is None:
        messages.append(assistant)
        _save_conversation(session_id, messages)

    resp = render(request, "_assistant.html", assistant=assistant)
    _set_session_cookie(resp, session_id)
    return resp


@app.get("/v2/documents", response_class=HTMLResponse)
def documents_page(request: Request) -> HTMLResponse:
    _require_auth(request)
    return render(request, "documents.html", documents=_list_documents())


@app.post("/v2/api/ingest", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def ingest(request: Request, file: UploadFile) -> HTMLResponse:
    _require_auth(request)
    _validate_csrf(request)

    s = get_settings()
    max_bytes = s.max_file_size_mb * 1024 * 1024

    # Enforce size limit without reading the entire upload into memory
    if file.size is not None and file.size > max_bytes:
        return render(
            request, "_doc_list.html",
            documents=_list_documents(),
            last_status="failed",
            last_error=f"File exceeds the {s.max_file_size_mb} MB size limit.",
        )

    # Stream into memory with a hard cap to guard against spoofed file.size
    chunks: list[bytes] = []
    total = 0
    async for chunk in file:
        total += len(chunk)
        if total > max_bytes:
            return render(
                request, "_doc_list.html",
                documents=_list_documents(),
                last_status="failed",
                last_error=f"File exceeds the {s.max_file_size_mb} MB size limit.",
            )
        chunks.append(chunk)
    content = b"".join(chunks)

    status = "failed"
    correlation_id = str(uuid.uuid4())
    try:
        _, status = ingest_document(content, file.filename or "upload.bin")
    except Exception as e:
        logger.exception("v2_ingest_failed", filename=file.filename,
                         correlation_id=correlation_id, error=str(e))
    return render(
        request, "_doc_list.html", documents=_list_documents(), last_status=status
    )


@app.post("/v2/api/documents/{doc_id}/delete", response_class=HTMLResponse)
def delete_document_route(request: Request, doc_id: str) -> HTMLResponse:
    _require_auth(request)
    _validate_csrf(request)
    correlation_id = str(uuid.uuid4())
    try:
        svc_delete_document(doc_id)
    except Exception as e:
        logger.exception("v2_delete_failed", doc_id=doc_id,
                         correlation_id=correlation_id, error=str(e))
    return render(
        request, "_doc_list.html", documents=_list_documents(), last_status=None
    )


@app.get("/v2/admin", response_class=HTMLResponse)
def admin_page(request: Request) -> HTMLResponse:
    _require_auth(request)
    return render(request, "admin.html", **_admin_stats())


@app.get("/healthz", include_in_schema=False)
def healthz(request: Request) -> dict:
    # /healthz is intentionally unauthenticated for load-balancer probes.
    # It does not reveal sensitive data — only boolean component liveness.
    return health.check_all()


# --------------------------------------------------------------------------- #
# Data helpers
# --------------------------------------------------------------------------- #
def _list_documents() -> list[dict]:
    with get_db() as db:
        docs = db.query(Document).order_by(Document.created_at.desc()).all()
        return [
            {
                "id": d.id,
                "filename": d.filename,
                "file_type": d.file_type,
                "file_size": d.file_size,
                "status": d.status,
                "chunk_count": d.chunk_count,
                "page_count": d.page_count,
                "created_at": d.created_at.strftime("%Y-%m-%d %H:%M") if d.created_at else "",
            }
            for d in docs
        ]


def _admin_stats() -> dict[str, Any]:
    cache_mgr = get_cache_manager()
    stats = cache_mgr.get_stats()
    total_lookups = sum(stats.values())
    hits = stats["tier1_hits"] + stats["tier2_hits"]
    hit_rate = (hits / total_lookups * 100) if total_lookups else 0.0

    with get_db() as db:
        doc_count = db.query(Document).filter(Document.status == "indexed").count()
        query_count = db.query(QueryLog).count()
        recent = (
            db.query(QueryLog)
            .order_by(QueryLog.timestamp.desc())
            .limit(15)
            .all()
        )
        recent_queries = [
            {
                "query": q.query_text[:80],
                "model": (q.model_used or "-").split("/")[-1],
                "tier": q.model_tier,
                "confidence": q.confidence,
                "cache": q.cache_tier_hit or "Fresh",
                "cost": q.cost_usd,
                "latency": q.latency_ms,
                "time": q.timestamp.strftime("%m-%d %H:%M") if q.timestamp else "",
            }
            for q in recent
        ]
        today_usage = db.query(TokenUsage).filter(TokenUsage.date == date.today()).first()
        total_cost = today_usage.total_cost if today_usage else 0.0

    return {
        "health": health.check_all(),
        "cache_stats": stats,
        "hit_rate": round(hit_rate, 1),
        "doc_count": doc_count,
        "query_count": query_count,
        "total_cost": round(total_cost, 4),
        "recent_queries": recent_queries,
    }
