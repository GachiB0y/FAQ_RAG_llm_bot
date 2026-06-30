from app.config import Settings
from .base import BaseLLMAdapter
from .openai import OpenAIAdapter
from .ollama import OllamaAdapter


def create_llm_adapter(settings: Settings) -> BaseLLMAdapter:
    if settings.LLM_PROVIDER == "openai":
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider")
        return OpenAIAdapter(api_key=settings.OPENAI_API_KEY)

    if settings.LLM_PROVIDER == "ollama":
        return OllamaAdapter(
            base_url=settings.OLLAMA_URL,
            model=settings.OLLAMA_MODEL,
            embedding_model=settings.EMBEDDING_MODEL,
        )

    raise ValueError(f"Unknown LLM provider: {settings.LLM_PROVIDER}")
