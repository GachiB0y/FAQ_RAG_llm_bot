from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from .base import BaseLLMAdapter


class OllamaAdapter(BaseLLMAdapter):
    def __init__(
        self, 
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2",
        embedding_model: str = "nomic-embed-text"
    ):
        self.base_url = base_url
        self.model = model
        self.embedding_model = embedding_model

    def get_llm(self):
        return Ollama(
            base_url=self.base_url,
            model=self.model,
            temperature=0.1,
            request_timeout=600.0,
        )

    def get_embedding_model(self):
        return OllamaEmbedding(
            base_url=self.base_url,
            model_name=self.embedding_model,
        )
