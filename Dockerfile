# IntelRAG — Enterprise RAG AI Platform
# Multi-stage build: build stage installs deps, final stage is lean + non-root.

# ---- build stage ----
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
# Install only production deps (no dev extras) into a prefix we'll copy over
RUN pip install --no-cache-dir --prefix=/install -e . 2>/dev/null || \
    pip install --no-cache-dir --prefix=/install .

# ---- final stage ----
FROM python:3.11-slim

# Runtime-only system lib required by PyMuPDF / python-magic
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# Create data directories; they will be bind-mounted in compose
RUN mkdir -p /app/data/uploads /app/data/chroma /app/data

# Non-root user — never run the app as root
RUN useradd -r -u 1001 -g root intelrag && \
    chown -R intelrag:root /app/data && \
    chmod -R g+rw /app/data
USER intelrag

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

EXPOSE 8600

# Default: FastAPI v2 UI (the supported production interface)
# Streamlit UI (app/main.py) is disabled — see README.
CMD ["uvicorn", "web.server:app", "--host", "0.0.0.0", "--port", "8600", "--workers", "2"]
