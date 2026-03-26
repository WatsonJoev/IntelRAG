"""
Pytest fixtures: DB session, Redis (fakeredis), vector store, file store.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Force test env before any app imports
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/test_intelrag.db")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("FILE_STORE_PATH", "./data/test_uploads")
os.environ.setdefault("CHROMA_PERSIST_DIR", "./data/test_chroma")

from models.db import Base


@pytest.fixture(scope="session")
def db_engine():
    url = os.environ.get("DATABASE_URL", "sqlite:///./data/test_intelrag.db")
    Path(url.replace("sqlite:///", "").split("?")[0]).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine) -> Generator[Session, None, None]:
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def redis_client():
    """Use fakeredis when REDIS_URL is not set."""
    try:
        import redis
        url = os.environ.get("REDIS_URL", "")
        if url and url.startswith("redis://"):
            return redis.from_url(url)
    except Exception:
        pass
    try:
        import fakeredis
        return fakeredis.FakeRedis()
    except ImportError:
        return None


@pytest.fixture
def file_store(tmp_path):
    from core.storage.file_store import FileStore
    return FileStore(base_path=str(tmp_path / "uploads"))


@pytest.fixture
def sample_pdf_bytes():
    """Minimal valid PDF bytes for parser tests."""
    return b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj
xref
0 4
trailer<</Size 4/Root 1 0 R>>
startxref
0
%%EOF"""
