# M1 + M2 — OpenRouter-генератор в live + threadpool — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Перевести генератор ответов `/api/v1/chat` с локальной Ollama на облачный OpenRouter (`qwen/qwen3.6-plus`), сохранив эмбеддинги на локальном `bge-m3`, и сделать вызов RAG неблокирующим (`run_in_threadpool`).

**Architecture:** Развязываем генератор и embedding-модель через тонкий `CompositeAdapter` (генератор — по `LLM_PROVIDER`, эмбеддинги — по `EMBEDDING_PROVIDER`), собираемый только в фабрике. `RAGEngine`/`deps`/`ingest` не меняются (интерфейс `BaseLLMAdapter` тот же). Генератор OpenRouter — через `OpenAILike` (OpenAI-совместимый API). M2 — обёртка `run_in_threadpool` вокруг синхронного `rag.query`.

**Tech Stack:** Python 3.11, FastAPI/Starlette, LlamaIndex (`OpenAILike`, `OllamaEmbedding`), pydantic-settings, pytest (`asyncio_mode=auto`).

## Global Constraints

- Спека (источник требований): `docs/superpowers/specs/2026-07-16-m1-m2-openrouter-live-design.md`.
- **Инвариант:** embedding-модель остаётся `bge-m3` (Ollama). В облако уходит ТОЛЬКО генератор. Контейнер `ollama` не гасим.
- Генератор live по умолчанию: **`qwen/qwen3.6-plus`** (конфигурируемо; B4 позже подтвердит слаг). Ключ — `OPENROUTER_API_KEY` (уже в конфиге с E4).
- OpenRouter base URL: `https://openrouter.ai/api/v1`.
- Surgical: `RAGEngine`, `deps.get_rag_engine`, `scripts/ingest_*` НЕ меняем (интерфейс адаптера сохраняем). Обратная совместимость: `LLM_PROVIDER=ollama` + `EMBEDDING_PROVIDER=ollama` → поведение как сейчас.
- `import OpenAILike` — ЛЕНИВЫЙ (внутри `get_llm`), чтобы загрузка модуля и тест `NotImplementedError` не зависели от пакета. (Пакет `llama-index-llms-openai-like` уже в образе — Dockerfile синкает `--group eval`; отдельный rebuild не нужен.)
- **Тесты запускать В контейнере:** `docker exec faq_rag_llm_bot-backend-1 bash -lc 'cd /app && /opt/venv/bin/python -m pytest <path> -q'`. Локальный `backend/` bind-mount в `/app`. Стек должен быть поднят (`make up`). Локальный `uv`/`python` не работают.
- Пред-существующая базовая «шумиха» (НЕ регрессии): `tests/test_config.py::test_settings_loads_defaults` падает в контейнере (docker-compose ставит `LLM_PROVIDER=ollama`); passlib `DeprecationWarning`.

---

## Файловая структура

**Создаём:**
- `backend/app/core/llm/openrouter.py` — `OpenRouterAdapter` (генератор через OpenAILike).
- `backend/app/core/llm/composite.py` — `CompositeAdapter` (делегирует llm/embeddings разным адаптерам).
- Тесты: `backend/tests/test_openrouter_adapter.py`, `test_composite_adapter.py`, `test_llm_factory.py`.

**Модифицируем:**
- `backend/app/config.py` — `openrouter` в `LLM_PROVIDER`, поле `OPENROUTER_GEN_MODEL`.
- `backend/app/core/llm/factory.py` — split на `_build_generator`/`_build_embedder`, `create_llm_adapter` → `CompositeAdapter`.
- `backend/app/core/llm/__init__.py` — экспорт новых классов.
- `backend/app/api/v1/chat.py` — `run_in_threadpool(rag.query, ...)`.
- `backend/tests/test_chat_gateway_integration.py` — подтвердить 200 через threadpool (спай на rag.query).
- `docker-compose.yml` — `LLM_PROVIDER=openrouter` + `OPENROUTER_*` env.
- `backend/tests/test_config.py` — дефолт `OPENROUTER_GEN_MODEL`.
- `PROJECT_STATUS.md` — галочки M1/M2/E3.

---

### Task 1: Config — провайдер `openrouter` + `OPENROUTER_GEN_MODEL`

**Files:**
- Modify: `backend/app/config.py:18` (LLM_PROVIDER Literal) и блок LLM
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `Settings.LLM_PROVIDER` принимает `"openrouter"`; `Settings.OPENROUTER_GEN_MODEL: str = "qwen/qwen3.6-plus"`. Используется в Task 4 (фабрика).

- [ ] **Step 1: Написать падающий тест дефолта**

Добавить в `backend/tests/test_config.py`:

```python
def test_openrouter_generator_defaults():
    from app.config import Settings
    s = Settings(
        DATABASE_URL="postgresql+asyncpg://x",
        REDIS_URL="redis://x",
        QDRANT_URL="http://x",
        JWT_SECRET="secret",
        LLM_PROVIDER="openrouter",
    )
    assert s.LLM_PROVIDER == "openrouter"
    assert s.OPENROUTER_GEN_MODEL == "qwen/qwen3.6-plus"
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `docker exec faq_rag_llm_bot-backend-1 bash -lc 'cd /app && /opt/venv/bin/python -m pytest tests/test_config.py::test_openrouter_generator_defaults -q'`
Expected: FAIL (`openrouter` не в Literal → ValidationError; и/или нет поля).

- [ ] **Step 3: Добавить провайдер и поле**

В `backend/app/config.py` заменить строку:

```python
    LLM_PROVIDER: Literal["openai", "anthropic", "ollama"] = "openai"
```
на:
```python
    LLM_PROVIDER: Literal["openai", "anthropic", "ollama", "openrouter"] = "openai"
```

И в блоке `# LLM` после `RAG_GENERATOR_MODEL: str = "gpt-4o-mini"` добавить:

```python
    # Слаг генератора для openrouter-провайдера (OpenRouter-слаг, напр. qwen/qwen3.6-plus).
    # Дефолт — текущий выбор; B4 подтвердит/сменит. См. docs/plans/2026-07-08-model-flow.md.
    OPENROUTER_GEN_MODEL: str = "qwen/qwen3.6-plus"
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `docker exec faq_rag_llm_bot-backend-1 bash -lc 'cd /app && /opt/venv/bin/python -m pytest tests/test_config.py -q'`
Expected: PASS (кроме пред-существующего `test_settings_loads_defaults`).

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/tests/test_config.py
git commit -m "feat(llm): провайдер openrouter + OPENROUTER_GEN_MODEL в конфиге (M1)"
```

---

### Task 2: `OpenRouterAdapter`

**Files:**
- Create: `backend/app/core/llm/openrouter.py`
- Test: `backend/tests/test_openrouter_adapter.py`

**Interfaces:**
- Consumes: `BaseLLMAdapter` (`app.core.llm.base`).
- Produces: `OpenRouterAdapter(api_key: str, model: str)`; `get_llm()` → `OpenAILike` на OpenRouter; `get_embedding_model()` → `raise NotImplementedError`. Используется в Task 4.

- [ ] **Step 1: Написать падающие тесты**

`backend/tests/test_openrouter_adapter.py`:

```python
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
```

(Если у `OpenAILike` имя атрибута отличается — напр. `api_base` хранится иначе — поправить ассерт под фактическое поле, не меняя реализацию.)

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `docker exec faq_rag_llm_bot-backend-1 bash -lc 'cd /app && /opt/venv/bin/python -m pytest tests/test_openrouter_adapter.py -q'`
Expected: FAIL (`ModuleNotFoundError: app.core.llm.openrouter`).

- [ ] **Step 3: Реализовать openrouter.py**

`backend/app/core/llm/openrouter.py`:

```python
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
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `docker exec faq_rag_llm_bot-backend-1 bash -lc 'cd /app && /opt/venv/bin/python -m pytest tests/test_openrouter_adapter.py -v'`
Expected: PASS (2 теста).

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/llm/openrouter.py backend/tests/test_openrouter_adapter.py
git commit -m "feat(llm): OpenRouterAdapter — генератор через OpenAILike (M1)"
```

---

### Task 3: `CompositeAdapter`

**Files:**
- Create: `backend/app/core/llm/composite.py`
- Test: `backend/tests/test_composite_adapter.py`

**Interfaces:**
- Consumes: `BaseLLMAdapter`.
- Produces: `CompositeAdapter(generator: BaseLLMAdapter, embedder: BaseLLMAdapter)`; `get_llm()` → `generator.get_llm()`; `get_embedding_model()` → `embedder.get_embedding_model()`. Используется в Task 4.

- [ ] **Step 1: Написать падающие тесты**

`backend/tests/test_composite_adapter.py`:

```python
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
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `docker exec faq_rag_llm_bot-backend-1 bash -lc 'cd /app && /opt/venv/bin/python -m pytest tests/test_composite_adapter.py -q'`
Expected: FAIL (`ModuleNotFoundError: app.core.llm.composite`).

- [ ] **Step 3: Реализовать composite.py**

`backend/app/core/llm/composite.py`:

```python
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
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `docker exec faq_rag_llm_bot-backend-1 bash -lc 'cd /app && /opt/venv/bin/python -m pytest tests/test_composite_adapter.py -v'`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/llm/composite.py backend/tests/test_composite_adapter.py
git commit -m "feat(llm): CompositeAdapter — развязка генератора и эмбеддингов (M1)"
```

---

### Task 4: Фабрика — split + `CompositeAdapter`

**Files:**
- Modify: `backend/app/core/llm/factory.py` (полностью переписываем тело)
- Modify: `backend/app/core/llm/__init__.py` (экспорт)
- Test: `backend/tests/test_llm_factory.py`

**Interfaces:**
- Consumes: `OpenRouterAdapter` (Task 2), `CompositeAdapter` (Task 3), `OpenAIAdapter`, `OllamaAdapter`, `Settings.LLM_PROVIDER`/`EMBEDDING_PROVIDER`/`OPENROUTER_GEN_MODEL`/`OPENROUTER_API_KEY`/`OLLAMA_URL`/`OLLAMA_MODEL`/`EMBEDDING_MODEL`/`OPENAI_API_KEY`/`RAG_GENERATOR_MODEL`.
- Produces: `create_llm_adapter(settings) -> CompositeAdapter`. Используется `deps.get_rag_engine` (без изменений).

- [ ] **Step 1: Написать падающие тесты**

`backend/tests/test_llm_factory.py`:

```python
from types import SimpleNamespace

import pytest

from app.core.llm.composite import CompositeAdapter
from app.core.llm.factory import create_llm_adapter
from app.core.llm.ollama import OllamaAdapter
from app.core.llm.openrouter import OpenRouterAdapter


def _settings(**over):
    base = dict(
        LLM_PROVIDER="ollama",
        EMBEDDING_PROVIDER="ollama",
        OPENROUTER_API_KEY=None,
        OPENROUTER_GEN_MODEL="qwen/qwen3.6-plus",
        OPENAI_API_KEY=None,
        RAG_GENERATOR_MODEL="gpt-4o-mini",
        OLLAMA_URL="http://ollama:11434",
        OLLAMA_MODEL="qwen3:1.7b",
        EMBEDDING_MODEL="bge-m3",
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_openrouter_generator_with_ollama_embeddings():
    adapter = create_llm_adapter(
        _settings(LLM_PROVIDER="openrouter", OPENROUTER_API_KEY="sk-x")
    )
    assert isinstance(adapter, CompositeAdapter)
    assert isinstance(adapter._generator, OpenRouterAdapter)
    assert isinstance(adapter._embedder, OllamaAdapter)
    assert adapter._generator.model == "qwen/qwen3.6-plus"
    assert adapter._embedder.embedding_model == "bge-m3"


def test_openrouter_requires_api_key():
    with pytest.raises(ValueError):
        create_llm_adapter(_settings(LLM_PROVIDER="openrouter", OPENROUTER_API_KEY=None))


def test_ollama_ollama_backward_compat():
    adapter = create_llm_adapter(_settings())
    assert isinstance(adapter, CompositeAdapter)
    assert isinstance(adapter._generator, OllamaAdapter)
    assert isinstance(adapter._embedder, OllamaAdapter)
    assert adapter._embedder.embedding_model == "bge-m3"
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `docker exec faq_rag_llm_bot-backend-1 bash -lc 'cd /app && /opt/venv/bin/python -m pytest tests/test_llm_factory.py -q'`
Expected: FAIL (нет `CompositeAdapter`-поведения / `_generator`).

- [ ] **Step 3: Переписать factory.py**

`backend/app/core/llm/factory.py` (полностью):

```python
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
```

- [ ] **Step 4: Обновить экспорт**

В `backend/app/core/llm/__init__.py` добавить экспорт новых классов. Текущий:

```python
from .base import BaseLLMAdapter
from .openai import OpenAIAdapter
from .factory import create_llm_adapter

__all__ = ["BaseLLMAdapter", "OpenAIAdapter", "create_llm_adapter"]
```

заменить на:

```python
from .base import BaseLLMAdapter
from .openai import OpenAIAdapter
from .ollama import OllamaAdapter
from .openrouter import OpenRouterAdapter
from .composite import CompositeAdapter
from .factory import create_llm_adapter

__all__ = [
    "BaseLLMAdapter",
    "OpenAIAdapter",
    "OllamaAdapter",
    "OpenRouterAdapter",
    "CompositeAdapter",
    "create_llm_adapter",
]
```

- [ ] **Step 5: Запустить — убедиться, что проходит**

Run: `docker exec faq_rag_llm_bot-backend-1 bash -lc 'cd /app && /opt/venv/bin/python -m pytest tests/test_llm_factory.py -v'`
Expected: PASS (3 теста).

- [ ] **Step 6: Регрессия — весь набор**

Run: `docker exec faq_rag_llm_bot-backend-1 bash -lc 'cd /app && /opt/venv/bin/python -m pytest -q'`
Expected: PASS (только пред-существующий `test_settings_loads_defaults` красный).

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/llm/factory.py backend/app/core/llm/__init__.py backend/tests/test_llm_factory.py
git commit -m "feat(llm): фабрика собирает CompositeAdapter (генератор⊥эмбеддинги) (M1)"
```

---

### Task 5: M2 — `run_in_threadpool` для `rag.query`

**Files:**
- Modify: `backend/app/api/v1/chat.py` (импорт + вызов внутри `trace_context`)
- Test: `backend/tests/test_chat_gateway_integration.py` (спай на rag.query)

**Interfaces:**
- Consumes: `starlette.concurrency.run_in_threadpool`; существующий `rag.query(message, chat_history=...)`.
- Produces: поведение эндпоинта не меняется (тот же ответ), но `rag.query` уходит в тред-пул.

- [ ] **Step 1: Добавить падающий тест-спай**

В `backend/tests/test_chat_gateway_integration.py` заменить класс `_FakeRag` так, чтобы фиксировать аргументы вызова (для проверки, что query вызван с сообщением), и добавить тест. Заменить определение `_FakeRag`:

```python
class _FakeRag:
    similarity_threshold = 0.7

    def __init__(self):
        self.calls = []

    def query(self, message, chat_history=None):
        self.calls.append((message, chat_history))
        return {"answer": "тестовый ответ", "sources": [], "confidence": 0.9}
```

и добавить тест (использует существующую фикстуру `client`, но нам нужен доступ к инстансу rag — если фикстура создаёт `_FakeRag()` инлайн в override, поменять override на общий инстанс). Конкретно: в фикстуре `client` заменить

```python
    app.dependency_overrides[get_rag_engine] = lambda: _FakeRag()
```
на
```python
    fake_rag = _FakeRag()
    app.dependency_overrides[get_rag_engine] = lambda: fake_rag
```
и в `yield` отдавать кортеж, ЛИБО (проще) добавить отдельный тест, который сам переопределяет rag. Проще — отдельный тест со своим override:

```python
def test_query_runs_and_returns_via_threadpool(monkeypatch):
    # Проверяем, что rag.query вызывается (через threadpool) и результат доходит.
    import app.api.v1.chat as chat_mod

    called = {}
    orig = chat_mod.run_in_threadpool

    async def spy(func, *args, **kwargs):
        called["ok"] = True
        return await orig(func, *args, **kwargs)

    monkeypatch.setattr(chat_mod, "run_in_threadpool", spy)
    # переиспользуем клиент-фикстуру через прямой вызов не выйдет; поэтому тест
    # живёт рядом с client-фикстурой и полагается на неё — см. Step 3 по месту.
```

> NB implementer: реализуй проверку в стиле уже существующих интеграционных тестов файла
> (фикстура `client`, `dependency_overrides`). Достаточно: (а) `test_clean_request_reaches_rag`
> остаётся зелёным (ответ доходит через threadpool); (б) один тест-спай подтверждает, что
> `chat.run_in_threadpool` реально вызывается на чистом запросе. Если удобнее — сделай
> `run_in_threadpool` спай через `monkeypatch.setattr("app.api.v1.chat.run_in_threadpool", ...)`
> и дергай существующий `client`. Не усложняй; главное — доказать факт вызова и возврат 200.

- [ ] **Step 2: Запустить — убедиться, что падает (спай не вызывается — ещё синхронно)**

Run: `docker exec faq_rag_llm_bot-backend-1 bash -lc 'cd /app && /opt/venv/bin/python -m pytest tests/test_chat_gateway_integration.py -q'`
Expected: FAIL на новом тесте (`run_in_threadpool` не импортирован/не вызывается).

- [ ] **Step 3: Внести правку в chat.py**

В `backend/app/api/v1/chat.py` добавить импорт (рядом с прочими):

```python
from starlette.concurrency import run_in_threadpool
```

Внутри `chat(...)`, в блоке `with trace_context(...)`, заменить синхронный вызов:

```python
        result = rag.query(data.message, chat_history=history)
```
на:
```python
        result = await run_in_threadpool(rag.query, data.message, chat_history=history)
```

(Остальное в блоке — `trace.update(...)` и т.д. — без изменений.)

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `docker exec faq_rag_llm_bot-backend-1 bash -lc 'cd /app && /opt/venv/bin/python -m pytest tests/test_chat_gateway_integration.py -v'`
Expected: PASS (все интеграционные, включая новый спай-тест).

- [ ] **Step 5: Проверка OTEL-контекста (ручная, без Langfuse-сети)**

Прочитать `backend/app/core/observability.py` и подтвердить: `trace_context` использует `start_as_current_span` (contextvars). `run_in_threadpool` → `anyio.to_thread.run_sync` копирует contextvars в тред → спан долетает. Зафиксировать вывод в отчёте (одна строка). Если при живом Langfuse-прогоне (позже) трейс генератора пропадёт — это отдельная правка, вне этой задачи.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/chat.py backend/tests/test_chat_gateway_integration.py
git commit -m "feat(chat): rag.query через run_in_threadpool — не блокировать event loop (M2)"
```

---

### Task 6: docker-compose — включить OpenRouter-генератор в live

**Files:**
- Modify: `docker-compose.yml` (env сервиса `backend`)

**Interfaces:**
- Consumes: `LLM_PROVIDER=openrouter`, `OPENROUTER_API_KEY`, `OPENROUTER_GEN_MODEL` из Task 1/4.

- [ ] **Step 1: Правка env**

В `docker-compose.yml`, сервис `backend`, заменить `- LLM_PROVIDER=ollama` на `- LLM_PROVIDER=openrouter` и добавить рядом:

```yaml
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY:-}
      - OPENROUTER_GEN_MODEL=${OPENROUTER_GEN_MODEL:-qwen/qwen3.6-plus}
```

Оставить без изменений: `EMBEDDING_PROVIDER=ollama`, `EMBEDDING_MODEL=bge-m3`, `OLLAMA_URL`, сервис `ollama` (нужен для эмбеддингов).

- [ ] **Step 2: Проверить, что ключ доступен docker-compose**

`OPENROUTER_API_KEY` должен быть в окружении, откуда запускается `docker compose` (в `.env` рядом с `docker-compose.yml`, либо `export`). NB: eval-ключ лежит в `.env.eval` — для live скопировать значение в `.env` или экспортировать в шелле. Проверить:

Run: `cd /Users/admin/Documents/project/FAQ_RAG_llm_bot && docker compose config | grep -E "LLM_PROVIDER|OPENROUTER_API_KEY|EMBEDDING_PROVIDER" | sed 's/\(OPENROUTER_API_KEY=\).*/\1<hidden>/'`
Expected: `LLM_PROVIDER=openrouter`, `EMBEDDING_PROVIDER=ollama`, `OPENROUTER_API_KEY` непустой.

- [ ] **Step 3: Перезапуск и boot-проверка**

Run: `cd /Users/admin/Documents/project/FAQ_RAG_llm_bot && docker compose up -d backend && sleep 5 && docker compose logs --tail=20 backend`
Expected: бэкенд стартует без ошибок фабрики; в логе `Starting FAQ RAG Bot with LLM provider: openrouter`.

- [ ] **Step 4: (ОПЦИОНАЛЬНО, тратит ~$0.003) живой smoke-тест**

⚠️ Тратит реальные токены OpenRouter — согласовать с пользователем (см. память «pre-flight before spending»). Только с валидным JWT admin-юзера. Проверить, что `/api/v1/chat` возвращает осмысленный русский ответ от `qwen/qwen3.6-plus` и `sources` не пустые. Если пользователь не хочет тратить — пропустить, задача считается выполненной по boot-проверке (Step 3).

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml
git commit -m "chore(compose): live-генератор OpenRouter qwen/qwen3.6-plus (M1); эмбеддинги остаются bge-m3"
```

---

### Task 7: Обновить PROJECT_STATUS.md + коммит плана

**Files:**
- Modify: `PROJECT_STATUS.md`

- [ ] **Step 1: Отметить сделанное**

В блоке «Линия E»/«план демо» отметить: **M1 (OpenRouter в live) ✅** и **M2 (`run_in_threadpool`) ✅**; в «Линия E → E3» отметить, что E3 закрывается M1+M2 (галочка или пометка «✅ через M1+M2»). Обновить «ТЕКУЩИЙ ФОКУС»: следующий шаг — **B4** (доказать выбор генератора; пользователь делает отдельным чатом) и/или **E1 (бот)**.

- [ ] **Step 2: Добавить строку в хронологию**

```markdown
| 16.07 | **M1+M2 ✅** — live-генератор переведён на OpenRouter `qwen/qwen3.6-plus` (эмбеддинги остались Ollama `bge-m3`): `OpenRouterAdapter` + `CompositeAdapter` (развязка генератор⊥эмбеддинги), фабрика собирает composite; `LLM_PROVIDER=openrouter` в compose (откат в 1 строку). `rag.query` в `run_in_threadpool` (не блокирует event loop). TDD: unit (адаптеры/фабрика) + integration. | [m1-m2-design](docs/superpowers/specs/2026-07-16-m1-m2-openrouter-live-design.md), [план](docs/superpowers/plans/2026-07-16-m1-m2-openrouter-live.md) |
```

- [ ] **Step 3: Закоммитить статус + план**

```bash
git add PROJECT_STATUS.md docs/superpowers/plans/2026-07-16-m1-m2-openrouter-live.md
git commit -m "docs(status): M1+M2 закрыты (OpenRouter live + threadpool)"
```

---

## Self-Review

**1. Spec coverage:**
- Провайдер `openrouter` + генератор через OpenAILike: Task 1 (конфиг) + Task 2 (адаптер). ✅
- Развязка генератор/эмбеддинги (CompositeAdapter): Task 3 + Task 4 (фабрика). ✅
- Инвариант bge-m3 (эмбеддинги локально): Task 4 `_build_embedder` + Task 6 (compose `EMBEDDING_PROVIDER=ollama`). ✅
- `get_embedding_model()` OpenRouter → NotImplementedError: Task 2. ✅
- `openrouter` без ключа → ValueError: Task 4. ✅
- Обратная совместимость ollama+ollama: Task 4. ✅
- Ленивый импорт OpenAILike: Task 2 (import внутри get_llm). ✅
- M2 run_in_threadpool + проверка OTEL-контекста: Task 5. ✅
- docker-compose переключение + откат: Task 6. ✅
- Вне объёма (B4, cloud-эмбеддинги, бот, graceful-фолбэк): не реализуем. ✅

**2. Placeholder scan:** Task 5 Step 1 намеренно даёт implementer свободу в форме спай-теста (в стиле существующего файла) — это не placeholder кода, а указание переиспользовать конкретную фикстуру `client`; критерий приёмки явный (спай на `app.api.v1.chat.run_in_threadpool` + 200). Остальные шаги — полный код.

**3. Type consistency:**
- `OpenRouterAdapter(api_key, model)` / `.model` / `.BASE_URL` — Task 2 определяет, Task 4 использует (`._generator.model`). ✅
- `CompositeAdapter(generator, embedder)` / `._generator` / `._embedder` — Task 3 определяет, Task 4 тесты читают эти атрибуты. ✅
- `create_llm_adapter(settings) -> CompositeAdapter` — Task 4; `deps.get_rag_engine` использует без изменений. ✅
- `OllamaAdapter.embedding_model` — существующий атрибут (ollama.py), Task 4 тесты его читают. ✅
- `run_in_threadpool` из `starlette.concurrency` — Task 5. ✅

Замечание: `OpenAILike` атрибуты (`.model`/`.api_base`/`.is_chat_model`) — pydantic-поля llama-index; если имя отличается, Task 2 Step 1 разрешает поправить ассерт под факт (не трогая реализацию).
