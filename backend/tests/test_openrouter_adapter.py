import pytest

from app.core.llm.openrouter import OpenRouterAdapter


def test_get_llm_configures_openai_like():
    from llama_index.llms.openai_like import OpenAILike

    adapter = OpenRouterAdapter(api_key="sk-test", model="qwen/qwen3.6-plus")
    llm = adapter.get_llm()

    assert isinstance(llm, OpenAILike)
    assert llm.model == "qwen/qwen3.6-plus"
    assert llm.api_base == "https://openrouter.ai/api/v1"
    assert llm.is_chat_model is True


def test_get_embedding_model_raises():
    adapter = OpenRouterAdapter(api_key="sk-test", model="qwen/qwen3.6-plus")
    with pytest.raises(NotImplementedError):
        adapter.get_embedding_model()
