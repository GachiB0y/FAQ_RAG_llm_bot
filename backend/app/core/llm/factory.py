from app.config import Settings
from .base import BaseLLMAdapter
from .openai import OpenAIAdapter
from .ollama import OllamaAdapter
from .openrouter import OpenRouterAdapter
from .composite import CompositeAdapter


def _build_generator(settings: Settings) -> BaseLLMAdapter:
    p = settings.LLM_PROVIDER
    if p == "openrouter":
        if not settings.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY is required for openrouter provider")
        return OpenRouterAdapter(
            api_key=settings.OPENROUTER_API_KEY,
            model=settings.OPENROUTER_GEN_MODEL,
        )
    if p == "openai":
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider")
        return OpenAIAdapter(api_key=settings.OPENAI_API_KEY, model=settings.RAG_GENERATOR_MODEL)
    if p == "ollama":
        return OllamaAdapter(
            base_url=settings.OLLAMA_URL,
            model=settings.OLLAMA_MODEL,
            embedding_model=settings.EMBEDDING_MODEL,
        )
    raise ValueError(f"Unknown LLM provider: {p}")


def _build_embedder(settings: Settings) -> BaseLLMAdapter:
    p = settings.EMBEDDING_PROVIDER
    if p == "ollama":
        return OllamaAdapter(
            base_url=settings.OLLAMA_URL,
            model=settings.OLLAMA_MODEL,
            embedding_model=settings.EMBEDDING_MODEL,
        )
    if p == "openai":
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required for OpenAI embeddings")
        return OpenAIAdapter(api_key=settings.OPENAI_API_KEY, model=settings.RAG_GENERATOR_MODEL)
    raise ValueError(f"Unknown embedding provider: {p}")


def create_llm_adapter(settings: Settings) -> BaseLLMAdapter:
    """Генератор из LLM_PROVIDER, эмбеддинги из EMBEDDING_PROVIDER → CompositeAdapter.
    RAGEngine получает единый BaseLLMAdapter — интерфейс не меняется."""
    return CompositeAdapter(_build_generator(settings), _build_embedder(settings))
