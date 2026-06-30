from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from .base import BaseLLMAdapter


class OpenAIAdapter(BaseLLMAdapter):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

    def get_llm(self):
        return OpenAI(
            api_key=self.api_key,
            model=self.model,
            temperature=0.1
        )

    def get_embedding_model(self):
        return OpenAIEmbedding(
            api_key=self.api_key,
            model="text-embedding-3-small"
        )
