# M1 + M2 — OpenRouter-генератор в live + threadpool (дизайн)

> **Статус:** черновик на ревью, 2026-07-16.
> **Контекст:** линия E / план демо в [PROJECT_STATUS.md](../../../PROJECT_STATUS.md).
> **Обоснование моделей/цен:** [model-flow](../../plans/2026-07-08-model-flow.md).

## Зачем

Два must-have пункта плана демо для user-facing контура `/api/v1/chat`:

- **M1** — заменить локальный генератор (Ollama `qwen3:1.7b`) на облачный
  (OpenRouter `qwen/qwen3.6-plus`): качество ответов (русский, юр-терминология) +
  конкурентность (облако параллелит инференс — узкое место, а не HTTP-слой).
- **M2** — `rag.query` сейчас синхронно блокирует event loop; обернуть в
  `run_in_threadpool`, чтобы ~10 конкурентных юзеров не выстраивались в очередь.

## Объём

- M1: провайдер `openrouter` для **генератора**; развязка генератора и
  embedding-модели; переключение через конфиг (`LLM_PROVIDER`).
- M2: неблокирующий вызов `rag.query` в chat-эндпоинте.

**Вне объёма** (YAGNI / отдельные задачи):
- **B4** — доказательное сравнение генераторов на golden-testset (отдельный чат).
  M1 берёт текущий выбор `qwen/qwen3.6-plus` как дефолт; B4 позже подтвердит/сменит слаг.
- Перенос **эмбеддингов** в облако (потребовал бы переиндексации; OpenRouter эмбеддинги
  не отдаёт) — остаются локально на Ollama `bge-m3`.
- Telegram-бот (E1), кэш ответов (E5), `run_in_threadpool` для других эндпоинтов.
- Graceful-обработка отказа OpenRouter сверх встроенных ретраев (см. «Обработка ошибок»).

## Ключевой инвариант — эмбеддинги остаются `bge-m3`

Коллекция Qdrant `documents` построена вектором `bge-m3` (1024 dim). Поиск корректен,
только если **вопрос кодируется той же моделью**, что и корпус. Поэтому:

```
эмбеддинги (поиск):  Ollama bge-m3           — ЛОКАЛЬНО, не меняем
генератор (ответы):  OpenRouter qwen/qwen3.6-plus — ОБЛАКО, новое
```

В облако уезжает **только генератор**. Контейнер `ollama` остаётся поднятым —
теперь ради `bge-m3` (эмбеддинги), а не ради генератора.

## Проблема в текущем коде

`create_llm_adapter` возвращает ОДИН адаптер, отдающий и генератор, и эмбеддинги из
одного провайдера. `EMBEDDING_PROVIDER` в конфиге объявлен, но фабрикой игнорируется —
сегодня эмбеддинги = `bge-m3` лишь потому, что весь адаптер Ollama. При смене генератора
на OpenRouter это ломается (у OpenRouter нет эмбеддингов). Нужно развязать источники.

## Дизайн M1 — Composite-адаптер

### Компоненты

1. **`OpenRouterAdapter`** (`backend/app/core/llm/openrouter.py`) — генератор.
   - `get_llm()` → `OpenAILike(api_base="https://openrouter.ai/api/v1", api_key=<key>,
     model=<slug>, is_chat_model=True, temperature=0.1, timeout=120, max_retries=3,
     additional_kwargs={"max_tokens": 1024})`. Паттерн уже проверен в `scripts/eval_rag.py`.
   - `get_embedding_model()` → `raise NotImplementedError("OpenRouter не отдаёт эмбеддинги —
     задайте EMBEDDING_PROVIDER=ollama")`. OpenRouter chat-only; эмбеддинги берутся из
     embedding-адаптера, не отсюда.

2. **`CompositeAdapter`** (`backend/app/core/llm/composite.py`) — тонкая обёртка над двумя
   адаптерами; сохраняет интерфейс `BaseLLMAdapter`, поэтому `RAGEngine`/`deps`/`ingest` не меняются.
   ```python
   class CompositeAdapter(BaseLLMAdapter):
       def __init__(self, generator: BaseLLMAdapter, embedder: BaseLLMAdapter):
           self._generator = generator
           self._embedder = embedder
       def get_llm(self):
           return self._generator.get_llm()
       def get_embedding_model(self):
           return self._embedder.get_embedding_model()
   ```

3. **Фабрика** (`backend/app/core/llm/factory.py`) — разбивается на выбор генератора
   (по `LLM_PROVIDER`) и эмбеддера (по `EMBEDDING_PROVIDER`), возвращает `CompositeAdapter`:
   ```python
   def _build_generator(settings) -> BaseLLMAdapter:
       p = settings.LLM_PROVIDER
       if p == "openrouter":
           if not settings.OPENROUTER_API_KEY:
               raise ValueError("OPENROUTER_API_KEY required for openrouter provider")
           return OpenRouterAdapter(api_key=settings.OPENROUTER_API_KEY,
                                    model=settings.OPENROUTER_GEN_MODEL)
       if p == "openai":
           if not settings.OPENAI_API_KEY:
               raise ValueError("OPENAI_API_KEY is required for OpenAI provider")
           return OpenAIAdapter(api_key=settings.OPENAI_API_KEY, model=settings.RAG_GENERATOR_MODEL)
       if p == "ollama":
           return OllamaAdapter(base_url=settings.OLLAMA_URL, model=settings.OLLAMA_MODEL,
                                embedding_model=settings.EMBEDDING_MODEL)
       raise ValueError(f"Unknown LLM provider: {p}")

   def _build_embedder(settings) -> BaseLLMAdapter:
       p = settings.EMBEDDING_PROVIDER
       if p == "ollama":
           return OllamaAdapter(base_url=settings.OLLAMA_URL, model=settings.OLLAMA_MODEL,
                                embedding_model=settings.EMBEDDING_MODEL)
       if p == "openai":
           if not settings.OPENAI_API_KEY:
               raise ValueError("OPENAI_API_KEY is required for OpenAI embeddings")
           return OpenAIAdapter(api_key=settings.OPENAI_API_KEY, model=settings.RAG_GENERATOR_MODEL)
       raise ValueError(f"Unknown embedding provider: {p}")

   def create_llm_adapter(settings) -> BaseLLMAdapter:
       return CompositeAdapter(_build_generator(settings), _build_embedder(settings))
   ```
   Обратная совместимость: при `LLM_PROVIDER=ollama` + `EMBEDDING_PROVIDER=ollama` это два
   `OllamaAdapter` → поведение идентично сегодняшнему. `anthropic` фабрика по-прежнему не
   реализует (как и сейчас — не в объёме).

### Конфиг (`backend/app/config.py`)

- `LLM_PROVIDER: Literal["openai", "anthropic", "ollama", "openrouter"]` — добавить `openrouter`.
- Новое: `OPENROUTER_GEN_MODEL: str = "qwen/qwen3.6-plus"` (слаг генератора для live; B4 позже
  подтвердит). `OPENROUTER_API_KEY` уже есть (добавлен в E4).

### Зависимости

`llama-index-llms-openai-like` сейчас только в eval-группе. Перенести/добавить в базовые
зависимости прод-бота (нужен для live-генератора). Обновить `uv.lock` + пересобрать образ.

### docker-compose (live-переключение)

Сервис `backend`: `LLM_PROVIDER=openrouter`, `EMBEDDING_PROVIDER=ollama` (уже так),
`EMBEDDING_MODEL=bge-m3` (уже так), добавить `OPENROUTER_API_KEY=${OPENROUTER_API_KEY:-}`
и опц. `OPENROUTER_GEN_MODEL`. Контейнер `ollama` **не гасим** (нужен для bge-m3).
Откат — одна строка `LLM_PROVIDER=ollama`.

## Дизайн M2 — неблокирующий `rag.query`

`backend/app/api/v1/chat.py`: заменить синхронный вызов внутри `trace_context`:
```python
from starlette.concurrency import run_in_threadpool
...
result = await run_in_threadpool(rag.query, data.message, chat_history=history)
```
`rag.query` остаётся синхронным (LlamaIndex-движок синхронный) — просто уходит в
тред-пул, не блокируя event loop. Порядок относительно gateway (E4) и персиста в БД
не меняется.

**Нюанс на проверку:** вызов внутри `trace_context` (OpenInference/OTEL-спан живёт в
contextvars). Starlette `run_in_threadpool` → `anyio.to_thread.run_sync`, который
**копирует contextvars** в тред → спан должен долетать. Проверяем при реализации: если
трейс генератора в Langfuse пропадёт — привязать контекст явно.

## Обработка ошибок

| Ситуация | Поведение |
|---|---|
| OpenRouter таймаут/5xx | `OpenAILike` ретраит (`max_retries=3`); при исчерпании — исключение → HTTP 500. Для демо приемлемо (graceful-фолбэк — вне объёма, кандидат в прод: авто-фолбэк на Ollama). |
| `LLM_PROVIDER=openrouter`, но нет `OPENROUTER_API_KEY` | Фабрика падает с внятной ошибкой при старте запроса (как текущая проверка `OPENAI_API_KEY`). |
| `get_embedding_model()` на OpenRouter-адаптере | `NotImplementedError` — защита от неверной конфигурации (эмбеддинги обязаны идти через embedder). |

## Тестирование (TDD)

**Unit (`backend/tests/`):**
- Фабрика: `LLM_PROVIDER=openrouter` + `EMBEDDING_PROVIDER=ollama` → `CompositeAdapter`, где
  `get_llm()` из OpenRouter, `get_embedding_model()` из Ollama (проверяем типы/параметры без сети).
- `openrouter` без `OPENROUTER_API_KEY` → `ValueError`.
- `OpenRouterAdapter.get_embedding_model()` → `NotImplementedError`.
- `CompositeAdapter` делегирует `get_llm`/`get_embedding_model` в нужные под-адаптеры (моками).
- Обратная совместимость: `ollama`+`ollama` → композит из двух OllamaAdapter (эмбеддинги bge-m3).
- Не дёргать реальные Ollama/OpenRouter — конструкторы `OpenAILike`/`OllamaEmbedding` не делают
  сетевых вызовов до использования; проверяем конфигурацию объектов.

**Integration:**
- `/api/v1/chat` с замоканным `rag.query` (как в тестах E4) остаётся 200, ответ проходит —
  подтверждает, что `run_in_threadpool(rag.query, ...)` вызывается и результат возвращается.
  Спай на `rag.query` подтверждает передачу `data.message` + `chat_history`.

## Интерфейсы (эскиз)

```python
# openrouter.py
class OpenRouterAdapter(BaseLLMAdapter):
    def __init__(self, api_key: str, model: str): ...
    def get_llm(self): ...                    # OpenAILike на OpenRouter
    def get_embedding_model(self):            # raise NotImplementedError

# composite.py
class CompositeAdapter(BaseLLMAdapter):
    def __init__(self, generator: BaseLLMAdapter, embedder: BaseLLMAdapter): ...
    def get_llm(self): ...                    # generator.get_llm()
    def get_embedding_model(self): ...        # embedder.get_embedding_model()

# factory.py
def create_llm_adapter(settings) -> BaseLLMAdapter:  # → CompositeAdapter(gen, emb)
```

## Откат / миграции

Данные не мигрируют (эмбеддинги те же, переиндексации нет). Откат генератора —
`LLM_PROVIDER=ollama` в docker-compose (мгновенно). Composite при этом ведёт себя как раньше.
