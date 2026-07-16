from .base import BaseLLMAdapter


class OpenRouterAdapter(BaseLLMAdapter):
    """Генератор через OpenRouter (OpenAI-совместимый API). Эмбеддинги OpenRouter
    не отдаёт — они приходят из отдельного embedding-адаптера (см. CompositeAdapter)."""

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def get_llm(self):
        from llama_index.llms.openai_like import OpenAILike

        return OpenAILike(
            api_base=self.BASE_URL,
            api_key=self.api_key,
            model=self.model,
            is_chat_model=True,
            temperature=0.1,
            timeout=120,
            max_retries=3,
            additional_kwargs={"max_tokens": 1024},
            default_headers={
                "HTTP-Referer": "https://github.com/faq-rag-llm-bot",
                "X-Title": "FAQ RAG live (generator)",
            },
        )

    def get_embedding_model(self):
        raise NotImplementedError(
            "OpenRouter не отдаёт эмбеддинги — задайте EMBEDDING_PROVIDER=ollama"
        )
