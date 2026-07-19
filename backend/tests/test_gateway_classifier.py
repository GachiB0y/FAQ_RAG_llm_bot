from types import SimpleNamespace

from app.core.gateway.classifier import build_openrouter_classifier


def test_returns_none_when_llm_disabled():
    settings = SimpleNamespace(
        INJECTION_GUARD_LLM_ENABLED=False,
        OPENROUTER_API_KEY="sk-xxx",
        INJECTION_GUARD_MODEL="google/gemini-3.1-flash-lite",
    )
    assert build_openrouter_classifier(settings) is None


def test_returns_none_when_key_missing():
    settings = SimpleNamespace(
        INJECTION_GUARD_LLM_ENABLED=True,
        OPENROUTER_API_KEY=None,
        INJECTION_GUARD_MODEL="google/gemini-3.1-flash-lite",
    )
    assert build_openrouter_classifier(settings) is None
