"""
SQLAlchemy ORM models and session for metadata DB.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all models."""

    type_annotation_map = {dict[str, Any]: JSON}


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    file_store_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String(64), ForeignKey("documents.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    char_offset: Mapped[int] = mapped_column(Integer, default=0)
    vector_store_id: Mapped[str] = mapped_column(String(256), nullable=False)
    text_preview: Mapped[str] = mapped_column(String(512), default="")

    document = relationship("Document", back_populates="chunks")


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    document_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), default="default")
    session_id: Mapped[str] = mapped_column(String(64), index=True, default="")
    messages_json: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Config(Base):
    __tablename__ = "config"

    key: Mapped[str] = mapped_column(String(256), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str] = mapped_column(String(128), default="")


class QueryLog(Base):
    __tablename__ = "query_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    session_id: Mapped[str] = mapped_column(String(64), default="")
    query_text: Mapped[str] = mapped_column(Text)
    model_used: Mapped[str] = mapped_column(String(128), default="")
    model_tier: Mapped[str] = mapped_column(String(16), default="")
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    cache_tier_hit: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    confidence: Mapped[str] = mapped_column(String(8), default="")
    fallback_tier: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    chunks_retrieved: Mapped[int] = mapped_column(Integer, default=0)


class TokenUsage(Base):
    __tablename__ = "token_usage"
    __table_args__ = (UniqueConstraint("date", name="uq_token_usage_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[datetime] = mapped_column(Date, index=True)
    tier_1_tokens: Mapped[int] = mapped_column(Integer, default=0)
    tier_2_tokens: Mapped[int] = mapped_column(Integer, default=0)
    tier_3_tokens: Mapped[int] = mapped_column(Integer, default=0)
    tier_1_cost: Mapped[float] = mapped_column(Float, default=0.0)
    tier_2_cost: Mapped[float] = mapped_column(Float, default=0.0)
    tier_3_cost: Mapped[float] = mapped_column(Float, default=0.0)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)


class IngestionLog(Base):
    __tablename__ = "ingestion_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String(64), ForeignKey("documents.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(16))
    chunks_created: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
