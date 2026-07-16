from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal, Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    REDIS_URL: str
    QDRANT_URL: str

    # JWT
    JWT_SECRET: str
    JWT_EXPIRE_MINUTES: int = 60

    # LLM
    LLM_PROVIDER: Literal["openai", "anthropic", "ollama"] = "openai"
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3:1.7b"
    # Модель генератора для openai-провайдера (bare OpenAI id, НЕ OpenRouter-слаг!).
    # Единый источник имени для прод-openai-пути вместо хардкода в адаптере.
    # NB: прод сейчас идёт через ollama (LLM_PROVIDER=ollama в docker-compose) — openai-путь
    # спящий. Прод на qwen/qwen3.6 через OpenRouter — B-линия (нужен OpenRouter/vLLM провайдер).
    RAG_GENERATOR_MODEL: str = "gpt-4o-mini"

    # Embeddings
    EMBEDDING_PROVIDER: Literal["openai", "ollama"] = "openai"
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # RAG
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50
    SIMILARITY_THRESHOLD: float = 0.7
    TOP_K_RESULTS: int = 5

    # Observability (Langfuse) — docs/superpowers/specs/2026-07-15-langfuse-observability-design.md
    LANGFUSE_ENABLED: bool = False
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_HOST: str = "http://localhost:3001"

    # Security Gateway (E4) — docs/superpowers/specs/2026-07-14-security-gateway-design.md
    GATEWAY_ENABLED: bool = True
    RATE_LIMIT_PER_DAY: int = 10
    INJECTION_GUARD_LLM_ENABLED: bool = False
    INJECTION_GUARD_MODEL: str = "google/gemini-3.1-flash-lite"
    OPENROUTER_API_KEY: Optional[str] = None

    # Upload
    UPLOAD_DIR: str = "/app/uploads"
    MAX_FILE_SIZE_MB: int = 50

    # Chat
    CHAT_HISTORY_RETENTION_DAYS: int = 90
    CHAT_HISTORY_PAGE_SIZE: int = 50

    model_config = SettingsConfigDict(env_file=".env")


def get_settings() -> Settings:
    return Settings()
