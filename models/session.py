"""
Database session factory and initialization.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import get_settings
from models.db import Base

_settings = get_settings()
_engine = create_engine(
    _settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in _settings.database_url else {},
    echo=_settings.environment == "development",
)
_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def init_db() -> None:
    """Create all tables. Safe to call on existing DB."""
    Base.metadata.create_all(bind=_engine)


def ensure_data_dir() -> None:
    """Ensure data directory exists for SQLite path."""
    url = _settings.database_url
    if url.startswith("sqlite:///") and "/" in url.replace("sqlite:///", ""):
        path = url.replace("sqlite:///", "").split("?")[0]
        Path(path).parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
