# Langfuse Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Self-hosted Langfuse видит каждый LLM-запрос обоих узлов (генератор + судья) с latency, токенами и фактической стоимостью, а Ragas-метрики ложатся на трейсы как Scores.

**Architecture:** Вся Langfuse-логика — в одном модуле `backend/app/core/observability.py` (вариант C: нативные интеграции ловят токены/стоимость, тонкая обёртка владеет идентичностью трейса и Scores). `engine.py` не трогаем; идентичность проставляем в местах вызова (`chat.py` для live, RAG-цикл в `eval_rag.py` для eval). Всё под флагом `LANGFUSE_ENABLED` (default `false`) — выключен → прозрачный no-op.

**Tech Stack:** Langfuse OSS (self-hosted, docker-compose), Python SDK v3, LlamaIndex-инструментор (генератор), LangChain CallbackHandler (судья в Ragas), pytest.

**Спека:** [2026-07-15-langfuse-observability-design.md](../specs/2026-07-15-langfuse-observability-design.md)

## Global Constraints

- **Флаг `LANGFUSE_ENABLED` (default `false`)** — единственный выключатель. Выключен → все функции модуля no-op, ноль обращений к сети/Langfuse.
- **Секреты** (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`) — только в `.env.eval` и env docker-compose, НИКОГДА в git.
- **Единый источник имён моделей** — `backend/models.env`; модуль своих дефолтов моделей не заводит.
- **Порт Langfuse UI = 3001** (3000 занят фронтом в `docker-compose.yml`).
- **Не трогаем `engine.py`** — идентичность трейса ставим в местах вызова (surgical changes).
- **Langfuse SDK — pin `langfuse>=3.0.0,<4.0.0`**; import-поверхность SDK изолирована внутри `observability.py`.
- Observability — побочный канал: её ошибки НЕ роняют ни запрос пользователя, ни прогон eval.

---

### Task 1: Инфраструктура — зависимость, compose, Makefile, конфиг, env ✅ ВЫПОЛНЕНО 2026-07-15

Поднять Langfuse и подготовить все точки конфигурации. Кода-логики нет — инфраструктура, на которой стоят остальные задачи. Deliverable: `make langfuse-up` поднимает UI на `localhost:3001`, `langfuse` импортируется в backend-контейнере.

> **Факты реализации (2026-07-15):** langfuse **3.15.0** в deps + uv.lock; Langfuse **3.213.0** (образы) поднят, health OK на :3001. Правки сверх исходного плана:
> - `docker-compose.langfuse.yml`: добавлен `name: langfuse` (отдельный проект, нет orphan-warning); `CLICKHOUSE_CLUSTER_ENABLED=false` в web+worker (иначе CH-миграции падают на `ON CLUSTER`/ReplicatedMergeTree на одиночном ClickHouse); `LANGFUSE_INIT_*` — headless-бутстрап org/проекта/юзера + предзаданные ключи (`pk-lf-faqrag-local`/`sk-lf-faqrag-local`), UI-логин `admin@faqrag.local` / `faqrag-local-pw`.
> - Ключи прописаны в `.env.eval`.
> - ⚠️ Task 2 (см. ниже): `langfuse.llama_index.LlamaIndexInstrumentor` в v3 удалён → генератор через OpenInference (`openinference-instrumentation-llama-index`).

**Files:**
- Modify: `backend/pyproject.toml` (добавить `langfuse` в основные deps)
- Create: `docker-compose.langfuse.yml`
- Modify: `Makefile` (цели `langfuse-up`/`langfuse-down` + env для eval-целей)
- Modify: `backend/app/config.py` (поля Langfuse в `Settings`)
- Modify: `docker-compose.yml` (env backend-сервиса)
- Modify: `.env.eval` (ключи Langfuse — локально, не в git)

**Interfaces:**
- Produces: env-контракт `LANGFUSE_ENABLED`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`, `LANGFUSE_TRACING_ENVIRONMENT`, `GIT_COMMIT`; `Settings.LANGFUSE_*` для live-пути.

- [ ] **Step 1: Добавить `langfuse` в основные зависимости**

В `backend/pyproject.toml`, в массив `[project] dependencies`, добавить строку (в конец списка, перед закрывающей `]`):

```toml
    "langfuse>=3.0.0,<4.0.0",
```

Основные deps (не `eval`-группа), потому что live-путь (`chat.py`) тоже импортирует модуль.

- [ ] **Step 2: Пересобрать образ и smoke-проверить импорт SDK**

```bash
docker compose build backend && docker compose up -d backend
docker exec faq_rag_llm_bot-backend-1 python -c "import langfuse; from langfuse import Langfuse; print('langfuse', langfuse.__version__)"
```
Expected: печатает версию `3.x`, без ImportError. Если import-пути интеграций в этой версии иные — зафиксировать здесь фактические пути, они понадобятся в Task 2 Step 3.

- [ ] **Step 3: Создать `docker-compose.langfuse.yml`**

Отдельный compose, порт UI **3001** (не 3000 — занят фронтом). Минимальный self-hosted набор (web + worker + postgres + clickhouse + redis + minio) по официальному образцу Langfuse v3:

```yaml
# Langfuse (OSS self-hosted) — отдельный стек, UI на localhost:3001.
# Поднять: make langfuse-up. Не мешает основному docker-compose.yml.
services:
  langfuse-web:
    image: langfuse/langfuse:3
    depends_on:
      - langfuse-db
      - clickhouse
    ports:
      - "3001:3000"
    environment:
      DATABASE_URL: postgresql://langfuse:langfuse@langfuse-db:5432/langfuse
      SALT: "changeme-local-salt"
      ENCRYPTION_KEY: "0000000000000000000000000000000000000000000000000000000000000000"
      NEXTAUTH_SECRET: "changeme-local"
      NEXTAUTH_URL: http://localhost:3001
      CLICKHOUSE_URL: http://clickhouse:8123
      CLICKHOUSE_USER: default
      CLICKHOUSE_PASSWORD: clickhouse
      REDIS_CONNECTION_STRING: redis://langfuse-redis:6379
      LANGFUSE_S3_EVENT_UPLOAD_BUCKET: langfuse
      LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT: http://langfuse-minio:9000
      LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID: minio
      LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY: miniosecret
      LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE: "true"
  langfuse-worker:
    image: langfuse/langfuse-worker:3
    depends_on:
      - langfuse-db
      - clickhouse
    environment:
      DATABASE_URL: postgresql://langfuse:langfuse@langfuse-db:5432/langfuse
      SALT: "changeme-local-salt"
      ENCRYPTION_KEY: "0000000000000000000000000000000000000000000000000000000000000000"
      CLICKHOUSE_URL: http://clickhouse:8123
      CLICKHOUSE_USER: default
      CLICKHOUSE_PASSWORD: clickhouse
      REDIS_CONNECTION_STRING: redis://langfuse-redis:6379
      LANGFUSE_S3_EVENT_UPLOAD_BUCKET: langfuse
      LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT: http://langfuse-minio:9000
      LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID: minio
      LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY: miniosecret
      LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE: "true"
  langfuse-db:
    image: postgres:16
    environment:
      POSTGRES_USER: langfuse
      POSTGRES_PASSWORD: langfuse
      POSTGRES_DB: langfuse
    volumes:
      - langfuse_pgdata:/var/lib/postgresql/data
  clickhouse:
    image: clickhouse/clickhouse-server:24
    environment:
      CLICKHOUSE_USER: default
      CLICKHOUSE_PASSWORD: clickhouse
    volumes:
      - langfuse_clickhouse:/var/lib/clickhouse
  langfuse-redis:
    image: redis:7
  langfuse-minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minio
      MINIO_ROOT_PASSWORD: miniosecret
    volumes:
      - langfuse_minio:/data

volumes:
  langfuse_pgdata:
  langfuse_clickhouse:
  langfuse_minio:
```

> Точный набор переменных сверить с актуальным `docker-compose.yml` из репозитория Langfuse под запиненную версию (self-hosting docs). Значения выше — локальные dev-заглушки, не для прода.

- [ ] **Step 4: Добавить цели в `Makefile`**

В `.PHONY` (строки 24-25) дописать `langfuse-up langfuse-down`. Затем добавить цели рядом с `mlflow-ui` (после строки 86):

```makefile
langfuse-up: ## Поднять Langfuse (UI на localhost:3001)
	docker compose -f docker-compose.langfuse.yml up -d
	@echo ">> Langfuse UI: http://localhost:3001 (создай проект → ключи в .env.eval)"

langfuse-down: ## Остановить Langfuse
	docker compose -f docker-compose.langfuse.yml down
```

- [ ] **Step 5: Прокинуть Langfuse-env в eval-цели `Makefile`**

Читать ключи из `.env.eval` (как `OPENROUTER_KEY`, строка 9). После строки 9 добавить:

```makefile
LANGFUSE_PUBLIC := $(shell grep '^LANGFUSE_PUBLIC_KEY=' .env.eval 2>/dev/null | cut -d= -f2-)
LANGFUSE_SECRET := $(shell grep '^LANGFUSE_SECRET_KEY=' .env.eval 2>/dev/null | cut -d= -f2-)
LANGFUSE_HOST ?= http://host.docker.internal:3001
LANGFUSE_ENABLED ?= false
GIT_COMMIT := $(shell git rev-parse --short HEAD 2>/dev/null)
```

В блок `EVAL_ENV` (строки 20-22) дописать (перенос строки `\` в конце предыдущей):

```makefile
	-e LANGFUSE_ENABLED="$(LANGFUSE_ENABLED)" \
	-e LANGFUSE_PUBLIC_KEY="$(LANGFUSE_PUBLIC)" \
	-e LANGFUSE_SECRET_KEY="$(LANGFUSE_SECRET)" \
	-e LANGFUSE_HOST="$(LANGFUSE_HOST)" \
	-e LANGFUSE_TRACING_ENVIRONMENT=eval \
	-e GIT_COMMIT="$(GIT_COMMIT)"
```

> `host.docker.internal` — из backend-контейнера достучаться до Langfuse на хосте (Docker Desktop on Mac поддерживает). Включение на прогон: `make eval-dense LANGFUSE_ENABLED=true`.

- [ ] **Step 6: Добавить поля Langfuse в `Settings`**

В `backend/app/config.py`, в класс `Settings` (после блока `# RAG`, перед `# Upload`):

```python
    # Observability (Langfuse) — см. docs/superpowers/specs/2026-07-15-langfuse-observability-design.md
    LANGFUSE_ENABLED: bool = False
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_HOST: str = "http://localhost:3001"
```

- [ ] **Step 7: Добавить env в backend-сервис `docker-compose.yml`**

В `docker-compose.yml`, в `backend.environment` (после строки 15), дописать:

```yaml
      - LANGFUSE_ENABLED=${LANGFUSE_ENABLED:-false}
      - LANGFUSE_PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY:-}
      - LANGFUSE_SECRET_KEY=${LANGFUSE_SECRET_KEY:-}
      - LANGFUSE_HOST=http://host.docker.internal:3001
      - LANGFUSE_TRACING_ENVIRONMENT=production
```

- [ ] **Step 8: Добавить ключи-заглушки в `.env.eval`**

В `.env.eval` дописать (значения подставишь из Langfuse UI после `make langfuse-up` → создания проекта):

```
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

- [ ] **Step 9: Проверить поднятие Langfuse**

```bash
make langfuse-up
sleep 20 && curl -sf http://localhost:3001/api/public/health && echo " OK"
```
Expected: `{"status":"OK"}` (или 200) → UI жив. Затем открыть `http://localhost:3001`, создать аккаунт + проект, скопировать ключи в `.env.eval`.

- [ ] **Step 10: Commit**

```bash
git add backend/pyproject.toml docker-compose.langfuse.yml Makefile backend/app/config.py docker-compose.yml
git commit -m "infra(langfuse): compose (port 3001) + Makefile targets + Settings/env для A3"
```
(`.env.eval` в gitignore — не коммитим.)

---

### Task 2: Модуль `observability.py` + unit-тесты ✅ ВЫПОЛНЕНО 2026-07-15

> **Факты (2026-07-15):** модуль написан под фактический v3-API (`start_as_current_span`,
> `update_current_trace`, `get_current_trace_id`, `create_score`, `flush`). Генератор —
> через `openinference-instrumentation-llama-index` (v4.4.3, добавлен в deps+lock), т.к.
> `langfuse.llama_index` в v3 удалён. 8 unit-тестов зелёные (флаг-off no-op + enabled через
> fake-client). Enabled-путь проверен end-to-end против живого Langfuse: трейс с
> user_id/session_id/tags/metadata + Scores долетел (environment=eval подхватился из env).
> Пред-существующий `test_config::test_settings_loads_defaults` падает в контейнере из-за
> env-оверрайдов docker-compose (LLM_PROVIDER=ollama, SIMILARITY_THRESHOLD=0.5) — НЕ связан
> с A3, не трогаем.

Ядро фичи: единственная точка Langfuse-логики. TDD. Флаг-off = прозрачный no-op — это и есть главное проверяемое свойство. Deliverable: модуль с проходящими unit-тестами.

**Files:**
- Create: `backend/app/core/observability.py`
- Test: `backend/tests/test_observability.py`

**Interfaces:**
- Produces:
  - `prompt_hash(text: str) -> str` — короткий (8 симв.) стабильный sha256-хэш
  - `init_observability(enabled: bool, public_key: str|None, secret_key: str|None, host: str|None) -> bool` — идемпотентно; возвращает фактический флаг
  - `trace_context(user_id: str|None=None, session_id: str|None=None, tags: list[str]|None=None, metadata: dict|None=None)` — context manager, yield-ит `TraceHandle`
  - `TraceHandle.id -> str|None`; `TraceHandle.update(metadata: dict|None=None) -> None`
  - `push_scores(trace_id: str|None, scores: dict[str, float]) -> None`
  - `langchain_callbacks() -> list` — колбэки для `ragas.evaluate(callbacks=...)`; пусто при выключенном
  - `flush() -> None`

- [ ] **Step 1: Написать падающие тесты (флаг-off + prompt_hash)**

Создать `backend/tests/test_observability.py`:

```python
import math
from app.core import observability as obs


def setup_function():
    # каждый тест стартует с чистого выключенного состояния
    obs._client = None
    obs._enabled = False
    obs._lf_callback = None


def test_prompt_hash_deterministic_and_short():
    h1 = obs.prompt_hash("hello prompt")
    h2 = obs.prompt_hash("hello prompt")
    assert h1 == h2
    assert len(h1) == 8
    assert obs.prompt_hash("other") != h1


def test_init_disabled_returns_false():
    assert obs.init_observability(False, None, None, None) is False
    assert obs._enabled is False
    assert obs._client is None


def test_trace_context_disabled_is_noop():
    with obs.trace_context(user_id="u1", session_id="s1", tags=["dense"]) as h:
        assert h.id is None
        h.update(metadata={"confidence": 0.9})  # не должно падать


def test_push_scores_disabled_noop():
    obs.push_scores(None, {"faithfulness": 0.8})  # не должно падать/слать сеть


def test_langchain_callbacks_disabled_empty():
    assert obs.langchain_callbacks() == []


def test_push_scores_enabled_maps_and_skips_nan(monkeypatch):
    calls = []

    class FakeClient:
        def create_score(self, trace_id, name, value):
            calls.append((trace_id, name, value))

    obs._enabled = True
    obs._client = FakeClient()
    obs.push_scores("trace-123", {"faithfulness": 0.9, "answer_relevancy": math.nan, "recall": None})

    assert ("trace-123", "faithfulness", 0.9) in calls
    assert all(name != "answer_relevancy" for _, name, _ in calls)  # NaN пропущен
    assert all(name != "recall" for _, name, _ in calls)            # None пропущен
```

- [ ] **Step 2: Запустить тесты — убедиться, что падают**

```bash
docker exec faq_rag_llm_bot-backend-1 python -m pytest tests/test_observability.py -v
```
Expected: FAIL — `ModuleNotFoundError: app.core.observability` / нет функций.

- [ ] **Step 3: Реализовать модуль**

Создать `backend/app/core/observability.py`. Весь импорт SDK — ленивый, внутри `init_observability`, чтобы флаг-off путь не тянул langfuse и был zero-overhead:

```python
"""Единственная точка Langfuse-логики (задача A3).

Вариант C: нативные интеграции ловят токены/стоимость, эта обёртка владеет
идентичностью трейса и Scores. Флаг LANGFUSE_ENABLED выключен → всё no-op.
Спека: docs/superpowers/specs/2026-07-15-langfuse-observability-design.md
"""
import hashlib
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

_client = None          # Langfuse client или None
_enabled = False
_lf_callback = None     # LangChain CallbackHandler (судья) или None


def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def init_observability(enabled, public_key=None, secret_key=None, host=None) -> bool:
    """Идемпотентно. enabled=False → no-op. Ошибка инициализации → тихо выключаемся
    (observability не должна ронять систему)."""
    global _client, _enabled, _lf_callback
    if not enabled:
        _enabled = False
        return False
    if _client is not None:
        return True
    try:
        from langfuse import Langfuse
        from langfuse.llama_index import LlamaIndexInstrumentor
        from langfuse.langchain import CallbackHandler
        _client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
        LlamaIndexInstrumentor().start()
        _lf_callback = CallbackHandler()
        _enabled = True
        logger.info("Langfuse observability enabled (host=%s)", host)
        return True
    except Exception as exc:
        logger.warning("Langfuse init failed → observability disabled: %s", exc)
        _client = None
        _enabled = False
        return False


class TraceHandle:
    def __init__(self, span=None):
        self._span = span

    @property
    def id(self):
        return getattr(self._span, "trace_id", None) if self._span else None

    def update(self, metadata=None):
        if self._span and metadata:
            self._span.update_trace(metadata=metadata)


@contextmanager
def trace_context(user_id=None, session_id=None, tags=None, metadata=None):
    if not _enabled or _client is None:
        yield TraceHandle(None)
        return
    with _client.start_as_current_span(name="rag-query") as span:
        span.update_trace(
            user_id=user_id,
            session_id=session_id,
            tags=tags or [],
            metadata=metadata or {},
        )
        yield TraceHandle(span)


def push_scores(trace_id, scores):
    if not (_enabled and _client and trace_id):
        return
    for name, value in scores.items():
        if value is None or (isinstance(value, float) and value != value):  # None / NaN
            continue
        _client.create_score(trace_id=trace_id, name=name, value=float(value))


def langchain_callbacks():
    return [_lf_callback] if (_enabled and _lf_callback) else []


def flush():
    if _enabled and _client:
        _client.flush()
```

> **SDK-версия — ФАКТ (проверено на langfuse 3.15.0, 2026-07-15):**
> - `langfuse.Langfuse` ✅, `langfuse.langchain.CallbackHandler` (судья) ✅, `langfuse.get_client` ✅, `langfuse.observe` ✅.
> - ⚠️ `langfuse.llama_index.LlamaIndexInstrumentor` **УДАЛЁН в v3** — его больше нет.
>   Генератор (LlamaIndex) в v3 инструментируется через **OpenInference**:
>   ```python
>   from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
>   LlamaIndexInstrumentor().instrument()   # шлёт OTEL-спаны в Langfuse-клиент
>   ```
>   → в `backend/pyproject.toml` добавить dep `openinference-instrumentation-llama-index`,
>   в `init_observability` заменить импорт инструментора на openinference-вариант.
> - Методы обёртки под v3: `client.start_as_current_span(...)`, `span.update_trace(...)`,
>   `client.create_score(...)`, `span.trace_id`, `client.flush()` — сверить на реализации Task 2.
> Правки ТОЛЬКО в `observability.py` + одна строка в pyproject (интерфейс §Interfaces неизменен).

- [ ] **Step 4: Запустить тесты — убедиться, что проходят**

```bash
docker exec faq_rag_llm_bot-backend-1 python -m pytest tests/test_observability.py -v
```
Expected: PASS (6 тестов).

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/observability.py backend/tests/test_observability.py
git commit -m "feat(obs): модуль observability (флаг-off no-op) + unit-тесты"
```

---

### Task 3: Инструментация eval-контура ✅ ВЫПОЛНЕНО 2026-07-16

> **Факты (2026-07-16):** `eval_rag.py` инструментирован. Отклонение от плана (чище):
> `lf_trace_id` держим ОТДЕЛЬНЫМ списком `lf_trace_ids`, а НЕ кладём в `samples` — тогда
> кэш RAG-ответов и `EvaluationDataset.from_list(samples)` остаются нетронутыми (иначе в
> кэш попадали бы stale trace_id от прошлого прогона). Step 4 плана (clean_samples) стал не
> нужен. Кэш-ветка: `lf_trace_ids=[None]*len` → из кэша Scores не шлём (трейсов генератора
> нет). Синтаксис/импорт проверены, флаг-off по умолчанию. Реальный прогон — Task 5.

Обернуть RAG-цикл в `trace_context`, прокинуть judge-колбэки в `ragas.evaluate`, повесить Ragas-метрики как Scores. Deliverable: включённый прогон eval создаёт трейсы генератора + судьи и Scores по вопросам.

**Files:**
- Modify: `backend/scripts/eval_rag.py`

**Interfaces:**
- Consumes: `init_observability`, `trace_context`, `push_scores`, `langchain_callbacks`, `flush`, `prompt_hash` (Task 2); env из Task 1.

- [ ] **Step 1: Импорты и чтение env в начале `eval_rag.py`**

После существующего блока env (после строки 87, `OLLAMA_JUDGE_MODEL`), добавить:

```python
sys.path.insert(0, "/app")  # уже есть выше — не дублировать
from app.core.observability import (
    init_observability,
    trace_context,
    push_scores,
    langchain_callbacks,
    flush as obs_flush,
    prompt_hash,
)
from app.core.rag.engine import SYSTEM_PROMPT  # уже импортирован выше — не дублировать

LANGFUSE_ENABLED = os.environ.get("LANGFUSE_ENABLED", "false").lower() in {"1", "true", "yes"}
GIT_COMMIT = os.environ.get("GIT_COMMIT", "unknown")
```

- [ ] **Step 2: Инициализация + session_id в начале `main()`**

В `main()`, сразу после `rag_llm = make_rag_llm()` (строка 318), добавить:

```python
    init_observability(
        LANGFUSE_ENABLED,
        public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
        host=os.environ.get("LANGFUSE_HOST"),
    )
    # session_id связывает Langfuse-трейсы с прогоном MLflow (логируем как param ниже).
    # PID делает id уникальным между прогонами (Date/random недоступны — PID достаточно).
    lf_session_id = f"{DATASET_SOURCE}-{RETRIEVAL_MODE}-pid{os.getpid()}"
    gen_model_name = OPENROUTER_GEN_MODEL if GENERATOR_PROVIDER == "openrouter" else OLLAMA_GEN_MODEL
    judge_model_name = OPENROUTER_JUDGE_MODEL if JUDGE_PROVIDER == "openrouter" else OLLAMA_JUDGE_MODEL
```

- [ ] **Step 3: Обернуть RAG-цикл в трейсы + собрать trace_ids**

В RAG-фазе (цикл `for i, item in enumerate(items, 1):`, строки 367-385) — обернуть вызов `run_rag`. Заменить тело цикла на:

```python
        for i, item in enumerate(items, 1):
            q_preview = item["question"][:80] + ("…" if len(item["question"]) > 80 else "")
            print(f"   [{i}/{len(items)}] {q_preview}")
            with trace_context(
                user_id=f"eval:{item.get('synthesizer_name', '')}:{i}",
                session_id=lf_session_id,
                tags=[RETRIEVAL_MODE],
                metadata={
                    "generator_model": gen_model_name,
                    "judge_model": judge_model_name,
                    "top_k": TOP_K,
                    "git_commit": GIT_COMMIT,
                    "prompt_hash": prompt_hash(SYSTEM_PROMPT),
                },
            ) as trace:
                try:
                    answer, contexts = run_rag(item["question"], retriever, rag_llm)
                except Exception as e:
                    print(f"      [!] FAIL: {type(e).__name__}: {str(e)[:120]}")
                    failed_indices.append(i)
                    answer = "[Ошибка генерации: вопрос не отвечен]"
                    contexts = []
                trace.update(metadata={"chunks": len(contexts)})
            samples.append(
                {
                    "user_input": item["question"],
                    "retrieved_contexts": contexts,
                    "response": answer,
                    "reference": item["reference"],
                    "lf_trace_id": trace.id,
                }
            )
            synthesizers.append(item.get("synthesizer_name", ""))
```

> Кэш-путь (загрузка из `samples_cache`) генерацию НЕ прогоняет → трейсов генератора нет, `lf_trace_id` из кэша. Для проверки Langfuse запускать со свежим прогоном (удалить кэш или `SKIP_CACHE=true`). Отражено в Step 7.

- [ ] **Step 4: Сохранять/читать `lf_trace_id` в кэше и строить dataset без него**

`EvaluationDataset.from_list(samples)` (строка 402) не должен получить лишнее поле. Перед ним отделить trace_ids:

```python
    lf_trace_ids = [s.get("lf_trace_id") for s in samples]
    clean_samples = [{k: v for k, v in s.items() if k != "lf_trace_id"} for s in samples]
    dataset = EvaluationDataset.from_list(clean_samples)
```
(Заменить строку `dataset = EvaluationDataset.from_list(samples)` на этот блок.)

- [ ] **Step 5: Прокинуть judge-колбэки в `evaluate` + залогировать session_id**

Внутри `with mlflow.start_run()`, в `mlflow.log_params({...})` (строки 419-440) добавить в словарь строку:

```python
                "langfuse_session_id": lf_session_id,
```

В вызов `evaluate(...)` (строки 446-460) добавить аргумент `callbacks`:

```python
        result = evaluate(
            dataset=dataset,
            metrics=[
                Faithfulness(),
                AnswerRelevancy(),
                LLMContextPrecisionWithReference(),
                LLMContextRecall(),
            ],
            llm=judge_llm,
            embeddings=judge_emb,
            run_config=RunConfig(max_workers=1, timeout=600, max_retries=3),
            show_progress=True,
            raise_exceptions=False,
            callbacks=langchain_callbacks(),
        )
```

- [ ] **Step 6: Повесить Ragas-метрики как Scores + flush**

После вычисления `numeric_cols` и печати сводки (после строки 488), перед `print(f"\n>> MLflow run_id...")`, добавить:

```python
        if any(lf_trace_ids) and len(lf_trace_ids) == len(df):
            for idx, tid in enumerate(lf_trace_ids):
                if not tid:
                    continue
                row = df.iloc[idx]
                push_scores(tid, {c: row[c] for c in numeric_cols})
            print(">> Scores отправлены в Langfuse")
        obs_flush()
```

- [ ] **Step 7: Проверить синтаксис и dry-run (флаг off → ничего не меняется)**

```bash
docker exec faq_rag_llm_bot-backend-1 python -c "import ast; ast.parse(open('/app/scripts/eval_rag.py').read()); print('syntax OK')"
```
Expected: `syntax OK`. Полный прогон с трейсами — в Task 5 (нужны ключи из UI).

- [ ] **Step 8: Commit**

```bash
git add backend/scripts/eval_rag.py
git commit -m "feat(obs): инструментация eval-контура — трейсы генератора/судьи + Scores из Ragas"
```

---

### Task 4: Инструментация live-контура ✅ ВЫПОЛНЕНО 2026-07-16

> **Факты (2026-07-16):** `main.py` lifespan вызывает `init_observability(settings...)`;
> `chat.py` оборачивает `rag.query` в `trace_context` (user_id=user.id, session_id,
> tags=[dense], metadata prompt_hash + после ответа confidence/sources_count/not_found).
> `engine.py` не тронут. Приложение поднимается здоровым и с флагом on, и off; Settings
> парсит `LANGFUSE_ENABLED` из env (true→True, дефолт False). Полноценный живой трейс
> (аутентифицированный чат-запрос → трейс) — на Task 5/E1 (нужны auth + залитые данные).

Обернуть `rag.query()` в `chat.py` в `trace_context`, инициализировать observability на старте приложения. `engine.py` не трогаем. Deliverable: при включённом флаге запрос через `/api/v1/chat` создаёт трейс с идентичностью юзера/сессии.

**Files:**
- Modify: `backend/app/main.py` (init на старте)
- Modify: `backend/app/api/v1/chat.py` (обёртка вокруг `rag.query`)

**Interfaces:**
- Consumes: `init_observability`, `trace_context`, `prompt_hash` (Task 2); `Settings.LANGFUSE_*` (Task 1).

- [ ] **Step 1: Инициализация observability в lifespan**

В `backend/app/main.py`, в `lifespan` (после строки `settings = get_settings()`, строка 35), добавить:

```python
    from app.core.observability import init_observability
    init_observability(
        settings.LANGFUSE_ENABLED,
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )
```

- [ ] **Step 2: Обернуть `rag.query` в chat-эндпоинте**

В `backend/app/api/v1/chat.py`, добавить импорты (после строки 13, `from app.core.rag import RAGEngine`):

```python
from app.core.observability import trace_context, prompt_hash
from app.core.rag.engine import SYSTEM_PROMPT
```

Заменить строку `result = rag.query(data.message, chat_history=history)` (строка 51) на:

```python
    with trace_context(
        user_id=str(user.id),
        session_id=session_id,
        tags=["dense"],
        metadata={"prompt_hash": prompt_hash(SYSTEM_PROMPT)},
    ) as trace:
        result = rag.query(data.message, chat_history=history)
        trace.update(metadata={
            "confidence": result["confidence"],
            "sources_count": len(result["sources"]),
            "not_found": result["confidence"] < rag.similarity_threshold,
        })
```

- [ ] **Step 3: Проверить, что приложение поднимается (флаг off — путь не изменился)**

```bash
docker compose up -d backend
sleep 5 && curl -sf http://localhost:8000/health && echo " OK"
docker exec faq_rag_llm_bot-backend-1 python -c "import ast; ast.parse(open('/app/app/api/v1/chat.py').read()); ast.parse(open('/app/app/main.py').read()); print('syntax OK')"
```
Expected: `{"status":"healthy"} OK` и `syntax OK`. Флаг `LANGFUSE_ENABLED=false` → трейсы не шлются, чат работает как раньше.

- [ ] **Step 4: Commit**

```bash
git add backend/app/main.py backend/app/api/v1/chat.py
git commit -m "feat(obs): инструментация live-контура (chat.py) + init в lifespan"
```

---

### Task 5: Custom-прайсинг (A3.2), verify (A3.3), обновление статуса

Ручная настройка цен в Langfuse UI, реальный включённый прогон, сверка стоимости, обновление трекеров. Deliverable: в Langfuse UI видны трейсы + Scores + ненулевой cost, сверенный с OpenRouter; статус обновлён.

**Files:**
- Modify: `PROJECT_STATUS.md`
- Modify: `docs/plans/2026-07-06-mlops-implementation-status.md`

- [x] **Step 1: Задать custom model prices — СКРИПТОМ, не руками (A3.2)** ✅ 2026-07-15

Оформлено воспроизводимо (философия «всё в коде», лечим боль #1): `backend/scripts/langfuse_set_prices.py` + цель `make langfuse-prices`. Скрипт берёт слаги из `models.env` (через env), цены — из [model-flow](../../plans/2026-07-08-model-flow.md), POST-ит в `/api/public/models`. Идемпотентен (повторный запуск → skip). Заведены qwen/qwen3.6 (0.32/1.28), openai/gpt-5.4 (2.5/15), google/gemini-3.1-flash-lite (0.25/1.5). Смена цены после создания — в UI (Langfuse резервирует имя модели через soft-delete, пересоздать по имени нельзя).

- [ ] **Step 2: Свежий включённый прогон eval на 2-3 вопросах**

Убедиться, что ключи в `.env.eval` заполнены (из UI). Затем:

```bash
docker exec faq_rag_llm_bot-backend-1 rm -f /app/tests/eval/samples_*.json   # свежий RAG, не кэш
make eval-dense LANGFUSE_ENABLED=true
```
Expected: прогон проходит; в конце `>> Scores отправлены в Langfuse`.

- [ ] **Step 3: Проверить трейсы в UI (готово-когда из intro)**

В `localhost:3001` → Tracing: видны трейсы окружения `eval` с разбивкой retrieval → generation, latency, токены; на трейсах — Scores (faithfulness и др.); трейсы судьи с cost. Сессия = `lf_session_id`. Cost ненулевой (после Step 1).

- [ ] **Step 4: Сверка cost с OpenRouter (A3.3)**

Открыть activity-дашборд OpenRouter (ground truth) за период прогона. Сравнить суммарный cost с Langfuse. Сойдётся → доверяем Langfuse. $0 в Langfuse → прайс не задан (вернуться к Step 1).

- [ ] **Step 5: Обновить трекеры**

В `docs/plans/2026-07-06-mlops-implementation-status.md`: блок «YOU ARE HERE» + пункты Шага C (Langfuse) → `[x]`, добавить строку в «Лог сессий» (2026-07-15).

В `PROJECT_STATUS.md`: отметить `A3` (+ A3.1/A3.2/A3.3) как `[x]`, обновить «ТЕКУЩИЙ ФОКУС» (следующее — A4/DVC или A6/Prefect), добавить строку в «Хронологию» (2026-07-15, Langfuse A3).

- [ ] **Step 6: Commit**

```bash
git add PROJECT_STATUS.md docs/plans/2026-07-06-mlops-implementation-status.md
git commit -m "docs(status): A3 (Langfuse) выполнен — трейсы + Scores + cost сверен"
```

---

## Self-Review

**Spec coverage:**
- §1 границы (оба контура, флаг-off) → Task 1 (флаг/env), Task 3 (eval), Task 4 (live). ✅
- §2 модуль observability (init/trace_context/push_scores/prompt_hash) → Task 2. ✅
- §3 вариант C (LlamaIndexInstrumentor + LangChain CallbackHandler + Scores) → Task 2 Step 3 (init), Task 3 Step 5-6. ✅
- §4 схема трейсов (environment/user_id/session_id/tags/metadata/Scores/spans) → Task 3 (eval), Task 4 (live); environment — через `LANGFUSE_TRACING_ENVIRONMENT` (Task 1 Step 5/7). ✅
- §5 custom-прайсинг + сверка → Task 5 Step 1, 4. ✅
- §6 конфиг/секреты (.env.eval, compose, Makefile) → Task 1. ✅
- §7 обработка ошибок (init try/except, no-op, flush) → Task 2 Step 3 (try/except, flush), Task 3 Step 6 (obs_flush). ✅
- §8 тестирование → Task 2 (unit), Task 5 (ручной verify). ✅
- §9 критерии готовности → покрыты Task 1-5. ✅

**Placeholder scan:** Один намеренный verify-gate на import-пути SDK (Task 1 Step 2 → Task 2 Step 3) — не плейсхолдер, а изоляция версионно-зависимой поверхности с явной инструкцией. Значения compose помечены как локальные заглушки со сверкой по офиц. docs. Остальное — конкретный код/команды.

**Type consistency:** `trace_context(...) as trace` → `trace.id` / `trace.update(metadata=...)` — совпадает между Task 3/4 и определением `TraceHandle` в Task 2. `push_scores(trace_id, dict)`, `langchain_callbacks()`, `flush()` — сигнатуры едины. `init_observability(enabled, public_key, secret_key, host)` — одинаково вызывается в Task 3 (eval) и Task 4 (live). ✅
