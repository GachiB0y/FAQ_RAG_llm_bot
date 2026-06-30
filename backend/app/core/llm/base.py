from abc import ABC, abstractmethod
from llama_index.core.llms import LLM


class BaseLLMAdapter(ABC):
    @abstractmethod
    def get_llm(self) -> LLM:
        """Return LlamaIndex-compatible LLM instance."""
        pass

    @abstractmethod
    def get_embedding_model(self):
        """Return embedding model for vectorization."""
        pass
