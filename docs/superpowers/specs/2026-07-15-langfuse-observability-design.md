# Langfuse Observability — дизайн (задача A3)

**Дата:** 2026-07-15
**Задача:** A3 из [MLOps-трекера](../../plans/2026-07-06-mlops-implementation-status.md) — лечит боль #4 «нет мониторинга».
**Вводная (читать для контекста):** [langfuse-intro](../../plans/2026-07-08-langfuse-intro.md)
**Статус:** дизайн утверждён, реализация — отдельным планом.

---

## 1. Цель и границы

**Цель:** self-hosted Langfuse видит КАЖДЫЙ LLM-запрос обоих узлов (генератор + судья)
с разбивкой по шагам, latency, токенами и **фактической стоимостью в $**, а качество
из Ragas ложится на трейсы как Scores.

**Строим оба контура целиком, но не гоняем полусырое:**
1. Сначала — eval-контур (`eval_rag.py`): генератор + судья. Здесь ~95% стоимости, он
   запускается уже сейчас.
2. Затем — live-контур (`RAGEngine.query()`): тем же механизмом.
3. Реальные прогоны — **потом**, когда система под прод более-менее выстроена. По
   умолчанию инструментация **выключена** (`LANGFUSE_ENABLED=false`) — ноль накладных
   расходов, пока сознательно не включим.

**В границах:** docker-compose для Langfuse (OSS self-hosted), модуль observability,
инструментация обоих контуров, схема трейсов, Ragas-метрики как Scores, custom-прайсинг
OpenRouter-моделей, сверка cost с OpenRouter (A3.3).

**Вне границ (осознанно):** Langfuse Cloud; online-eval (faithfulness на семпле живого
трафика) — после появления трафика; 👍/👎 UI-фидбэк — вместе с E1 (Telegram); глубокая
ClickHouse-аналитика; DVC-версионирование промпта (шаг D) — здесь только кладём `prompt_hash`.

---

## 2. Архитектура

Вся Langfuse-логика — в одном тонком модуле; `engine.py` и `eval_rag.py` только импортируют
из него и остаются чистыми. Модуль — одна изолированная, тестируемая единица.

```
backend/app/core/observability.py
 ├── init_observability()        # конфиг клиента + запуск интеграций (идемпотентно)
 ├── trace_context(...)          # context manager: штампует идентичность трейса
 ├── push_scores(trace_id, {...})# вешает Ragas-метрики как Scores
 └── prompt_hash(text) -> str    # короткий стабильный хэш промпта
```

- **`init_observability()`** — читает env, при `LANGFUSE_ENABLED=false` делает no-op и
  возвращает флаг «выключено». При `true`: создаёт Langfuse-клиент, запускает
  `LlamaIndexInstrumentor` (генератор), готовит LangChain `CallbackHandler` (судья).
  Идемпотентна — повторный вызов не плодит интеграции.
- **`trace_context(environment, user_id, session_id, tags, metadata)`** — context manager
  поверх `@observe`/Langfuse-контекста; проставляет идентичность на текущий трейс. Вне
  включённого Langfuse — прозрачный no-op (просто выполняет тело).
- **`push_scores(trace_id, scores: dict)`** — принимает `{"faithfulness": 0.9, ...}`,
  создаёт Score на трейс. No-op при выключенном флаге.
- **`prompt_hash(text)`** — например первые 8 символов sha256; мост к будущему
  DVC-версионированию промпта (шаг D).

**Флаг как единственный выключатель:** `LANGFUSE_ENABLED` управляет всем. Выключен →
модуль полностью прозрачен (тесты, локальная разработка, CI не трогают Langfuse).

---

## 3. Механизм инструментации (вариант C — гибрид)

Нативная интеграция ловит **токены и стоимость** (то, что важно и что руками легко
испортить), тонкая обёртка **владеет идентичностью трейса и Scores**.

| Узел | Технология | Токены/стоимость (нативно) | Идентичность/Scores (обёртка) |
|---|---|---|---|
| Генератор | LlamaIndex `query_engine` | `LlamaIndexInstrumentor().start()` | `trace_context(...)` вокруг `query()`/`run_rag()` |
| Судья | Ragas → LangChain `ChatOpenAI` | `CallbackHandler` → `ragas.evaluate(callbacks=[...])` | трейс судьи внутри контекста прогона |

- Генератор течёт через LlamaIndex в обоих контурах → один `LlamaIndexInstrumentor`
  покрывает и eval, и live.
- Судья течёт через LangChain внутри Ragas → передаём Langfuse `CallbackHandler` в
  `ragas.evaluate(callbacks=[...])`.
- **Scores:** после `evaluate` идём по строкам `result.to_pandas()` (там per-question
  faithfulness / answer_relevancy / context_precision / recall) → `push_scores` на
  соответствующий трейс.

> **Проверить на реализации (не влияет на дизайн):** у Langfuse SDK разошлись v2 и v3
> (v3 на OpenTelemetry, API интеграций другой). Первый шаг реализации — зафиксировать
> версию в `pyproject` (группа eval) и сверить точные вызовы `LlamaIndexInstrumentor` /
> `CallbackHandler` / создания Score с этой версией. Абстракция модуля §2 скрывает выбор
> версии от `engine.py`/`eval_rag.py`.

---

## 4. Схема трейсов (что и как логируем)

| Поле | Eval-контур | Live-контур |
|---|---|---|
| `environment` | `"eval"` | `"production"` |
| `user_id` | `eval:{synthesizer}:{qN}` | telegram id (E1) / аноним пока |
| `session_id` | MLflow `run_id` (мост Langfuse ↔ MLflow-прогон) | id чат-сессии |
| `tags` | `[retrieval_mode]` (`dense`/`hybrid`) | `[retrieval_mode]` |
| `metadata` | `{gen_model, judge_model, top_k, git_commit, prompt_hash}` | `{confidence, sources_count, not_found, prompt_hash}` |
| **Scores** | Ragas-метрики по каждому вопросу | 👍/👎 (позже, с E1) + online-eval (позже) |

**Spans внутри трейса:**
- Eval: `retrieval` (output = chunks + scores + max_score) → `generation` (генератор,
  токены/стоимость) → судейские `generation` (метрики Ragas).
- Live: `retrieval` (output = chunks + scores + max_score) → `generation`.

**Почему так:**
- `session_id = MLflow run_id` в eval связывает observability с экспериментом: из
  Langfuse-сессии видно, к какому прогону MLflow относятся трейсы.
- Scores из Ragas — ради чего Langfuse у нас заигрывает: в UI по каждому вопросу видно
  качество рядом с ценой/latency → петля Фазы 8 (сортируешь по `faithfulness` → плохие
  ответы → в testset).
- `not_found` в live-metadata — видно, когда сработал порог `max_score < threshold`
  (`engine.py:66`) и бот сказал «не нашёл».
- `prompt_hash` — мост к DVC-версионированию промпта (шаг D).

**Не логируем (чтобы не захламлять):** полные тексты чанков в metadata (дубль span
output), локальные bge-m3 embeddings как узел стоимости (это $0 — шум), мелкие теги «на
всякий случай».

---

## 5. Стоимость: custom-прайсинг и сверка (A3.2 + A3.3)

- **A3.2 — custom model prices.** OpenRouter-имена (`qwen/…`, `openai/…`, `google/…`)
  в справочнике Langfuse отсутствуют → без прайса cost покажет $0 (токены есть, цены нет).
  Задать custom-цены в Langfuse UI по слагам из `backend/models.env`. Цены — из
  [model-flow](../../plans/2026-07-08-model-flow.md) и с openrouter.ai.
- **A3.3 — сверка (ground truth).** После первого включённого прогона eval сверить cost
  из Langfuse с activity-дашбордом OpenRouter. Сойдётся → доверяем Langfuse; $0 → прайс
  не задан (см. A3.2).

---

## 6. Конфигурация и секреты

- Ключи `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` — в `.env.eval`
  (рядом с OpenRouter, локально, в git не попадает).
- Флаг `LANGFUSE_ENABLED` (default `false`) — единственный выключатель инструментации.
- Langfuse-сервисы — отдельный `docker-compose.langfuse.yml` (web + worker + postgres +
  clickhouse), чтобы не мешать основному стеку. UI на `localhost:3000`.
- Makefile-цели: `make langfuse-up` / `make langfuse-down` (по образцу `mlflow-ui`).
- Модель-имена для трейсов берём из тех же env, что и `eval_rag.py` (единый источник —
  `backend/models.env`), своих дефолтов модуль не заводит.

---

## 7. Обработка ошибок

- **Langfuse недоступен / ошибка отправки:** не роняем запрос пользователя и не роняем
  прогон eval. Observability — побочный канал: ошибки логируются в предупреждение, но
  бизнес-путь продолжается. (Langfuse SDK шлёт трейсы асинхронно/батчами — это его модель.)
- **`LANGFUSE_ENABLED=false`:** все функции модуля — прозрачные no-op, ноль обращений к сети.
- **Флаш перед выходом:** в конце `eval_rag.py` (короткоживущий процесс) явно flush/shutdown
  клиента, иначе последние трейсы/Scores не успеют уйти.

---

## 8. Тестирование

- **Модуль observability (unit):** при `LANGFUSE_ENABLED=false` все функции — no-op и не
  дёргают сеть (мок клиента → 0 вызовов). `prompt_hash` стабилен и детерминирован.
- **`trace_context` (unit):** при включённом флаге проставляет ожидаемые поля (мок клиента,
  проверяем переданные аргументы).
- **`push_scores` (unit):** маппит dict метрик в вызовы создания Score (мок клиента).
- **Интеграционная проверка (ручная, verify):** включить флаг → `make eval-dense` на 2-3
  вопросах → в Langfuse UI видны трейсы (retrieval + generation), latency, токены,
  Scores по вопросам; после A3.2 — ненулевой cost. Это и есть «готово когда» из intro.

---

## 9. Критерии готовности

- [ ] `docker-compose.langfuse.yml` поднимает Langfuse, UI на `localhost:3000`.
- [ ] Модуль `observability.py` + unit-тесты (флаг-off = no-op).
- [ ] Eval-контур инструментирован: генератор (LlamaIndexInstrumentor) + судья
      (CallbackHandler в ragas.evaluate) + Scores из Ragas на трейсы.
- [ ] Live-контур (`RAGEngine.query()`) инструментирован тем же модулем.
- [ ] Custom-прайсинг OpenRouter-моделей задан (A3.2).
- [ ] Ручная verify: включённый прогон eval → трейсы + latency + токены + Scores в UI;
      cost сверён с OpenRouter (A3.3).
- [ ] `LANGFUSE_ENABLED=false` по умолчанию — система не гоняет инструментацию, пока не выстроена.

---

## 10. Связанные документы

- [langfuse-intro](../../plans/2026-07-08-langfuse-intro.md) — что/как/зачем, MLflow vs Langfuse
- [mlops-implementation-status](../../plans/2026-07-06-mlops-implementation-status.md) — трекер (шаг A3/C)
- [model-flow](../../plans/2026-07-08-model-flow.md) — модели и цены (для custom-прайсинга)
- `backend/models.env` — единый источник имён моделей
- Следствие: `user_id` в трейсах — фундамент под демо E1 (Telegram) и B4 (факт-цена прогонов)
