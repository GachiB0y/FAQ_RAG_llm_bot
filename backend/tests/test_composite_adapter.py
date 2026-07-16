from app.core.llm.base import BaseLLMAdapter
from app.core.llm.composite import CompositeAdapter


class _Gen(BaseLLMAdapter):
    def get_llm(self):
        return "GEN_LLM"

    def get_embedding_model(self):
        raise NotImplementedError


class _Emb(BaseLLMAdapter):
    def get_llm(self):
        raise AssertionError("embedder.get_llm must not be called")

    def get_embedding_model(self):
        return "EMB_MODEL"


def test_delegates_llm_to_generator_and_embeddings_to_embedder():
    adapter = CompositeAdapter(_Gen(), _Emb())
    assert adapter.get_llm() == "GEN_LLM"
    assert adapter.get_embedding_model() == "EMB_MODEL"
