"""
Application settings via pydantic-settings.
Profiles: development | staging | production
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """IntelRAG configuration. Load from env and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter="__",
    )

    # Environment
    environment: Literal["development", "staging", "production"] = Field(
        default="development", alias="ENVIRONMENT"
    )

    # OpenRouter
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", alias="OPENROUTER_BASE_URL"
    )
    openrouter_http_referer: str = Field(
        default="https://intelrag.example.com", alias="OPENROUTER_HTTP_REFERER"
    )
    openrouter_x_title: str = Field(default="IntelRAG", alias="OPENROUTER_X_TITLE")

    # Database
    database_url: str = Field(
        default="sqlite:///./data/intelrag.db", alias="DATABASE_URL"
    )
    db_user: str = Field(default="", alias="DB_USER")
    db_password: str = Field(default="", alias="DB_PASSWORD")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_max_memory: str = Field(default="4gb", alias="REDIS_MAX_MEMORY")

    # Vector store
    vector_store_backend: Literal["chromadb", "qdrant"] = Field(
        default="chromadb", alias="VECTOR_STORE_BACKEND"
    )
    chroma_persist_dir: str = Field(default="./data/chroma", alias="CHROMA_PERSIST_DIR")
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    qdrant_api_key: str = Field(default="", alias="QDRANT_API_KEY")

    # File store
    file_store_backend: Literal["local", "minio", "s3"] = Field(
        default="local", alias="FILE_STORE_BACKEND"
    )
    file_store_path: str = Field(default="./data/uploads", alias="FILE_STORE_PATH")

    # Embedding
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2", alias="EMBEDDING_MODEL"
    )
    embedding_dimension: int = Field(default=384, alias="EMBEDDING_DIMENSION")
    embedding_batch_size: int = Field(default=64, alias="EMBEDDING_BATCH_SIZE")

    # Chunking
    chunk_size: int = Field(default=1000, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, alias="CHUNK_OVERLAP")
    max_chunks_per_doc: int = Field(default=5000, alias="MAX_CHUNKS_PER_DOC")

    # Retrieval
    top_k_retrieval: int = Field(default=20, alias="TOP_K_RETRIEVAL")
    top_k_rerank: int = Field(default=5, alias="TOP_K_RERANK")
    similarity_threshold: float = Field(default=0.25, alias="SIMILARITY_THRESHOLD")
    hybrid_search: bool = Field(default=True, alias="HYBRID_SEARCH")

    # Model tiers (OpenRouter model IDs)
    tier_1_model: str = Field(
        default="meta-llama/llama-3.2-3b-instruct:free", alias="TIER_1_MODEL"
    )
    tier_2_model: str = Field(
        default="meta-llama/llama-3.3-70b-instruct:free", alias="TIER_2_MODEL"
    )
    tier_3_model: str = Field(default="openai/gpt-4o-mini", alias="TIER_3_MODEL")

    # LLM service
    llm_timeout_seconds: int = Field(default=60, alias="LLM_TIMEOUT_SECONDS")
    llm_max_retries: int = Field(default=3, alias="LLM_MAX_RETRIES")
    llm_retry_base_delay: float = Field(default=1.0, alias="LLM_RETRY_BASE_DELAY")

    # Conversation
    conversation_history_turns: int = Field(default=6, alias="CONVERSATION_HISTORY_TURNS")

    # Cache
    cache_exact_ttl: int = Field(default=86400, alias="CACHE_EXACT_TTL")
    cache_semantic_ttl: int = Field(default=172800, alias="CACHE_SEMANTIC_TTL")
    cache_semantic_similarity_threshold: float = Field(
        default=0.95, alias="CACHE_SEMANTIC_SIMILARITY_THRESHOLD"
    )

    # Limits
    max_file_size_mb: int = Field(default=200, alias="MAX_FILE_SIZE_MB")
    query_rate_limit_per_user: int = Field(
        default=100, alias="QUERY_RATE_LIMIT_PER_USER"
    )

    # Auth (Basic Auth — set both to enable)
    basic_auth_username: str = Field(default="", alias="BASIC_AUTH_USERNAME")
    basic_auth_password: str = Field(default="", alias="BASIC_AUTH_PASSWORD")
    secret_key: str = Field(default="change-me-in-production", alias="SECRET_KEY")

    # Cost circuit-breaker (0 = disabled)
    daily_cost_limit_usd: float = Field(default=0.0, alias="DAILY_COST_LIMIT_USD")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=True, alias="LOG_JSON")


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
