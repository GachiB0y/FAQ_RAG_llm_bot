# B4 — доказательный выбор прод-генератора (дизайн)

> **Статус:** черновик на ревью, 2026-07-19.
> **Контекст:** линия B / план демо в [PROJECT_STATUS.md](../../../PROJECT_STATUS.md).
> **Обоснование моделей/цен:** [model-flow](../../plans/2026-07-08-model-flow.md).
> **Конвенции MLflow:** скилл `tracking-experiments-with-mlflow`.

## Зачем

Прод-генератор (`qwen/qwen3.6-plus`) выбран по обзору цен и качеству русского «на
глаз» — но не доказан на **наших** данных. B4 закрывает этот пробел: гоняем
кандидатов на одном golden-testset через Ragas+MLflow с независимым судьёй
`openai/gpt-5.4` и фиксируем прод-конфиг с доказательством в MLflow. Это же —
витрина методологии тестирования для демо (линия E).

## Ключевой инсайт, определивший дизайн

4 Ragas-метрики измеряют **разные вещи**:

| Метрика | Что измеряет | От чего зависит |
|---|---|---|
| **Faithfulness** | ответ обоснован контекстом (нет галлюцинаций) | **генератор** |
| **AnswerRelevancy** | ответ отвечает на вопрос | **генератор** |
| **ContextPrecision** | доля релевантных чанков среди найденных | **retrieval** (top_k, chunk_size) |
| **ContextRecall** | retrieval достал всё нужное | **retrieval** (top_k, chunk_size) |

**Следствие:** при сравнении *генераторов* на фиксированном retrieval
`ContextPrecision/Recall` **не меняются** (чанки одинаковые у всех). Выбор
генератора решается по **Faithfulness + AnswerRelevancy + цена + скорость +
ручная проверка русского**. Context-метрики здесь — sanity-check (подтверждают,
что retrieval был идентичным) и «потолок» (низкий Recall → ни один генератор не
спасёт). Retrieval-оси (top_k, chunk_size) — отдельные этапы.

Второй факт: **n=11 вопросов** → дельты в 2-3 пункта внутри шума. Выводы B4 —
про явные разрывы, не про микро-дельты. Жёсткий числовой порог на n=11 —
самообман, поэтому quality-gate формулируем как «в пределах шума лучшего + глаза».

## Объём

**Стадийно — меняем ОДНУ ось за этап** (судья + датасет фиксированы всегда).

### Этап 1 — выбор генератора (этот дизайн, реализуем сейчас)

- **Кандидаты (3, все через OpenRouter, один ключ):**
  - `qwen/qwen3.6-plus` — текущий выбор
  - `deepseek/deepseek-v4-flash` — дешевле
  - `google/gemini-3.1-flash` — fallback
- **Фиксировано:** `top_k=5`, `temperature=0.1`, `retrieval_mode=dense`,
  эмбеддинги `bge-m3` (Ollama), chunk_size (текущий), судья `openai/gpt-5.4`,
  датасет `testset_golden.json` (11 в.).

### Вне объёма (отдельные задачи позже)

- **Этап 2** — свип `top_k` (3/5/10) на победителе Этапа 1. Здесь работают
  context-метрики + latency + cost. Ляжет как parent/child ран в MLflow.
- **Этап 3** — `chunk_size`/`overlap`: требует переиндексации корпуса в отдельную
  Qdrant-коллекцию на каждый размер. Тяжёлый, опциональный — только если Этапы 1-2
  оставят вопрос.
- **`temperature`/`prompt`** тюнинг, локальная модель (ждёт vLLM/B1 — Ollama
  `qwen3:1.7b` нестабилен, не прод-кандидат), **Promptfoo** (B5).

## Правило выбора победителя (цена/качество)

**Quality-gate + дешёвый/быстрый:**

1. Отсекаем модели, чьи `mean_faithfulness` / `mean_answer_relevancy` **заметно
   ниже** лучшего (с учётом шума n=11 — визуально по parallel-coordinates, не по
   жёсткому порогу).
2. Среди прошедших gate — берём **дешёвую/быструю** (cost из Langfuse, latency из
   MLflow).
3. **Тай-брейк — ручная проверка русского:** топ-2 кандидата смотрим глазами по
   per-question CSV на юр-терминологии ФПСР (требование
   [PROJECT_STATUS](../../../PROJECT_STATUS.md): «прогнать 10-15 вопросов глазами»).

## Как это выглядит в MLflow

**Новый эксперимент `b4-generator-selection`** — отдельно от учебного
`ragas-eval`, чтобы Compare-вью был apples-to-apples.

Этап 1 = **3 рана**, по одному на модель. Раскладка по слотам (скилл MLflow):

| Слот | Значение |
|---|---|
| **run_name** | короткое, только различитель: `qwen3.6-plus` / `deepseek-v4-flash` / `gemini-3.1-flash` |
| **params** | `generator_model`, `generator_provider`, `top_k=5`, `temperature=0.1`, `retrieval_mode=dense`, `embedding_model=bge-m3`, `judge_model`, `chunk_size`, `dataset_source`, `dataset_size=11` |
| **tags** | `git_commit`, `dataset_version=golden_v1`, `judge=gpt-5.4`, `purpose=b4-generator-selection`, `stage=1`, `langfuse_session_id` |
| **metrics** | `mean_faithfulness`, `mean_answer_relevancy`, `mean_context_precision`, `mean_context_recall`, `mean_latency_s` |
| **artifact** | per-question CSV (`eval_results_*.csv`) |
| **note** | `mlflow.note.content` — вывод по рану, заполняем после анализа |

**Cost** в MLflow **не логируем** — точный факт-cost уже есть в Langfuse (A3) по
`langfuse_session_id` (он же в params/tags → связь MLflow↔Langfuse). MLflow-метрика
только `mean_latency_s` (wall-clock, бесплатно). Сравнение: выбрать 3 рана →
**Compare → parallel-coordinates** по faithfulness/relevancy/latency; cost добираем
в Langfuse.

Этап 2 (позже) ляжет как **parent/child**: `topk-sweep` → `k3`/`k5`/`k10` (nested).

## Что правим в коде (хирургически)

Всё — в `backend/scripts/eval_rag.py` (+ Makefile). Существующий пайплайн
параметризован env; правки минимальны.

1. **`TOP_K` и `temperature` → из env** (сейчас захардкожены `5` / `0.1`). Нужно
   для Этапа 2 без правок кода.
2. **`run_name` → короткий** — слаг модели (сейчас длинный слаг
   `{source}-{mode}-{gen}-judge-{judge}-k{k}`, антипаттерн скилла). Детали уже в params.
3. **MLflow-теги** `git_commit`, `dataset_version`, `judge`, `purpose`, `stage`
   (сейчас их нет — ран нереплицируем/нефильтруем). Имя эксперимента — из env
   (дефолт `ragas-eval`, B4 передаёт `b4-generator-selection`).
4. **`mean_latency_s`** — замер wall-clock на вопрос в `run_rag`, среднее → метрика.
5. **Баг-фикс кэша (важно):** кэш RAG-ответов ключуется как
   `samples_{DATASET_SOURCE}_{RETRIEVAL_MODE}.json` — **без генератора и top_k**.
   Прогон 3 генераторов подряд подсунет ответы первого. Добавить в ключ кэша
   `generator_model` (слаг) + `top_k`.

## Прогон и результат

- Этап 1 = `make eval-golden GEN_MODEL=<модель>` ×3 (CLI переопределяет
  `backend/models.env`). Судья и датасет фиксированы целью `eval-golden`.
- Тонкий Makefile-target **`b4-stage1`** — прогоняет три модели подряд (для
  воспроизводимости демо; руками легко ошибиться слагом).
- **Стоимость:** ~$0.7/прогон судьи × 3 ≈ **$2.1** (Этап 1). Факт — в Langfuse.
- **Итог:** зафиксировать прод-генератор с доказательством → обновить
  `PROJECT_STATUS.md` (галочка B4 + модель в таблице моделей), вывод в `note` ранов.

## Критерии готовности (verify)

- [ ] `eval_rag.py`: `TOP_K`/`temperature`/имя эксперимента читаются из env;
      `run_name` короткий; теги `git_commit`/`dataset_version`/`judge`/`purpose`/`stage`
      проставлены; `mean_latency_s` логируется; ключ кэша включает генератор+top_k.
- [ ] `make b4-stage1` прогоняет 3 модели → 3 рана в эксперименте
      `b4-generator-selection`, метрики ненулевые, CSV-артефакт на каждом.
- [ ] Context-метрики ~равны у 3 ранов (подтверждение чистоты сравнения).
- [ ] Ручная проверка русского топ-2 сделана; вывод записан в `note` + PROJECT_STATUS.
