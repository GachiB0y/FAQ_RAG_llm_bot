from .base import BaseLLMAdapter


class CompositeAdapter(BaseLLMAdapter):
    """Генератор и embedding-модель из разных источников. Сохраняет интерфейс
    BaseLLMAdapter → RAGEngine/deps/ingest не меняются."""

    def __init__(self, generator: BaseLLMAdapter, embedder: BaseLLMAdapter):
        self._generator = generator
        self._embedder = embedder

    def get_llm(self):
        return self._generator.get_llm()

    def get_embedding_model(self):
        return self._embedder.get_embedding_model()
