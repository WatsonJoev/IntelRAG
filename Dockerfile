# IntelRAG — Enterprise RAG AI Platform
FROM python:3.11-slim

WORKDIR /app

# System deps for sentence-transformers / PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]" 2>/dev/null || pip install --no-cache-dir -e .

COPY . .

# Data dirs (mount volumes in compose)
RUN mkdir -p /app/data/uploads /app/data/chroma /app/data

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8501

CMD ["streamlit", "run", "app/main.py", "--server.port=8501", "--server.address=0.0.0.0"]
