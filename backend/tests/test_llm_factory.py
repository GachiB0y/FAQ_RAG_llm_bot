from types import SimpleNamespace

import pytest

from app.core.llm.composite import CompositeAdapter
from app.core.llm.factory import create_llm_adapter
from app.core.llm.ollama import OllamaAdapter
from app.core.llm.openrouter import OpenRouterAdapter


def _settings(**over):
    base = dict(
        LLM_PROVIDER="ollama",
        EMBEDDING_PROVIDER="ollama",
        OPENROUTER_API_KEY=None,
        OPENROUTER_GEN_MODEL="qwen/qwen3.6-plus",
        OPENAI_API_KEY=None,
        RAG_GENERATOR_MODEL="gpt-4o-mini",
        OLLAMA_URL="http://ollama:11434",
        OLLAMA_MODEL="qwen3:1.7b",
        EMBEDDING_MODEL="bge-m3",
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_openrouter_generator_with_ollama_embeddings():
    adapter = create_llm_adapter(
        _settings(LLM_PROVIDER="openrouter", OPENROUTER_API_KEY="sk-x")
    )
    assert isinstance(adapter, CompositeAdapter)
    assert isinstance(adapter._generator, OpenRouterAdapter)
    assert isinstance(adapter._embedder, OllamaAdapter)
    assert adapter._generator.model == "qwen/qwen3.6-plus"
    assert adapter._embedder.embedding_model == "bge-m3"


def test_openrouter_requires_api_key():
    with pytest.raises(ValueError):
        create_llm_adapter(_settings(LLM_PROVIDER="openrouter", OPENROUTER_API_KEY=None))


def test_ollama_ollama_backward_compat():
    adapter = create_llm_adapter(_settings())
    assert isinstance(adapter, CompositeAdapter)
    assert isinstance(adapter._generator, OllamaAdapter)
    assert isinstance(adapter._embedder, OllamaAdapter)
    assert adapter._embedder.embedding_model == "bge-m3"
