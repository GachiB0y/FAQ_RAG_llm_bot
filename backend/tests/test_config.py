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
