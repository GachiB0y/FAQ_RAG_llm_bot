import pytest
from app.config import Settings


def test_settings_loads_defaults():
    settings = Settings(
        DATABASE_URL="postgresql://test:test@localhost/test",
        REDIS_URL="redis://localhost",
        QDRANT_URL="http://localhost:6333",
        JWT_SECRET="test-secret",
    )
    assert settings.LLM_PROVIDER == "openai"
    assert settings.CHUNK_SIZE == 512
    assert settings.SIMILARITY_THRESHOLD == 0.7


def test_gateway_defaults(monkeypatch):
    # OPENROUTER_API_KEY теперь задаётся в docker-compose (M1, значение может быть пустым) —
    # чтобы проверить именно ДЕФОЛТ поля, убираем возможную переменную окружения.
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    s = Settings(
        DATABASE_URL="postgresql+asyncpg://x",
        REDIS_URL="redis://x",
        QDRANT_URL="http://x",
        JWT_SECRET="secret",
    )
    assert s.GATEWAY_ENABLED is True
    assert s.RATE_LIMIT_PER_DAY == 10
    assert s.INJECTION_GUARD_LLM_ENABLED is False
    assert s.INJECTION_GUARD_MODEL == "google/gemini-3.1-flash-lite"
    assert s.OPENROUTER_API_KEY is None


def test_openrouter_generator_defaults(monkeypatch):
    from app.config import Settings

    # OPENROUTER_GEN_MODEL задаётся в docker-compose — чтобы проверить именно ДЕФОЛТ
    # поля (B4-выбор), убираем возможную переменную окружения.
    monkeypatch.delenv("OPENROUTER_GEN_MODEL", raising=False)
    s = Settings(
        DATABASE_URL="postgresql+asyncpg://x",
        REDIS_URL="redis://x",
        QDRANT_URL="http://x",
        JWT_SECRET="secret",
        LLM_PROVIDER="openrouter",
    )
    assert s.LLM_PROVIDER == "openrouter"
    assert s.OPENROUTER_GEN_MODEL == "deepseek/deepseek-v4-flash"
