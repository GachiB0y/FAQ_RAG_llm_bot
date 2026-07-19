# B4 — доказательный выбор прод-генератора (Этап 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Прогнать 3 облачных генератора на golden-testset через Ragas+MLflow с судьёй `openai/gpt-5.4` и доказательно зафиксировать прод-генератор по правилу quality-gate + цена/скорость.

**Architecture:** Существующий скрипт `backend/scripts/eval_rag.py` уже параметризован env. Выносим чистую конфиг-логику (имя кэша, слаг модели, MLflow-теги) в новый тестируемый модуль `scripts/eval_config.py`, чиним баг ключа кэша, делаем `top_k`/`temperature`/имя-эксперимента env-driven, добавляем `mean_latency_s` и MLflow-теги воспроизводимости. Прогон трёх моделей — новый Makefile-target `b4-stage1`.

**Tech Stack:** Python 3.11, Ragas 0.2.15, MLflow (sqlite), LlamaIndex, OpenRouter (через `OpenAILike`), Langfuse (A3), pytest, Docker, Make.

## Global Constraints

- **Судья и датасет фиксированы** во всех прогонах Этапа 1: `openai/gpt-5.4` + `testset_golden.json` (11 в.). Менять только генератор.
- **Кандидаты (точные слаги):** `qwen/qwen3.6-plus`, `deepseek/deepseek-v4-flash`, `google/gemini-3.1-flash`.
- **Эмбеддинги не трогаем** — `bge-m3` локально (Ollama); коллекция `documents` под него.
- **Хирургические правки** — трогаем только строки под задачу; чужой стиль не меняем (CLAUDE.md §3).
- **Секреты** — `OPENROUTER_API_KEY`/`LANGFUSE_*` из `.env.eval`, в git не попадают.
- **Контейнер backend:** `faq_rag_llm_bot-backend-1`. Тесты: `docker exec faq_rag_llm_bot-backend-1 python -m pytest ...`.
- **Пред-флайт перед платным прогоном** (память `pre-flight-before-spending`): ключ/модели/Langfuse проверить и сделать смоук на 1 вопросе до полного цикла.

## File Structure

- **Create** `backend/scripts/eval_config.py` — чистые хелперы без тяжёлых импортов: `model_short`, `samples_cache_filename`, `build_mlflow_tags`. Единственная ответственность — детерминированная конфиг-логика, покрываемая юнит-тестами.
- **Create** `backend/tests/test_eval_config.py` — юнит-тесты для `eval_config`.
- **Modify** `backend/scripts/eval_rag.py` — использовать `eval_config`; env-driven `RAG_TOP_K`/`RAG_TEMPERATURE`/`MLFLOW_EXPERIMENT`/`DATASET_VERSION`/`EVAL_PURPOSE`/`EVAL_STAGE`; короткий `run_name`; `mlflow.set_tags(...)`; `mean_latency_s`.
- **Modify** `Makefile` — target `b4-stage1` (3 модели подряд с env под B4).
- **Modify** `PROJECT_STATUS.md` — по итогу: галочка B4, модель в таблице, вывод.

---

### Task 1: Тестируемый `eval_config` + фикс бага ключа кэша

**Files:**
- Create: `backend/scripts/eval_config.py`
- Test: `backend/tests/test_eval_config.py`
- Modify: `backend/scripts/eval_rag.py:382-384` (кэш-путь) и `:455-465` (вычисление `gen_short`)

**Interfaces:**
- Produces:
  - `model_short(model: str) -> str` — последний сегмент после `/`.
  - `samples_cache_filename(dataset_source: str, retrieval_mode: str, gen_short: str, top_k: int) -> str`
  - `build_mlflow_tags(*, git_commit, dataset_version, judge_model, purpose, stage, langfuse_session_id) -> dict`

- [ ] **Step 1: Написать падающий тест**

`backend/tests/test_eval_config.py`:
```python
import sys

sys.path.insert(0, "/app/scripts")  # eval_config живёт в scripts/, не в пакете app

from eval_config import build_mlflow_tags, model_short, samples_cache_filename


def test_model_short_strips_provider_prefix():
    assert model_short("deepseek/deepseek-v4-flash") == "deepseek-v4-flash"
    assert model_short("qwen3:1.7b") == "qwen3:1.7b"


def test_cache_filename_differs_per_generator():
    # Регрессия бага B4: один source+mode, разные модели → РАЗНЫЕ файлы.
    a = samples_cache_filename("json", "dense", "qwen3.6-plus", 5)
    b = samples_cache_filename("json", "dense", "deepseek-v4-flash", 5)
    assert a != b
    assert a == "samples_json_dense_qwen3.6-plus_k5.json"


def test_cache_filename_differs_per_top_k():
    assert samples_cache_filename("json", "dense", "qwen3.6-plus", 5) != \
        samples_cache_filename("json", "dense", "qwen3.6-plus", 10)


def test_build_mlflow_tags_has_required_keys():
    tags = build_mlflow_tags(
        git_commit="abc123",
        dataset_version="golden_v1",
        judge_model="openai/gpt-5.4",
        purpose="b4-generator-selection",
        stage="1",
        langfuse_session_id="eval-dense-x",
    )
    assert set(tags) >= {"git_commit", "dataset_version", "judge", "purpose", "stage"}
    assert tags["judge"] == "openai/gpt-5.4"
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run: `docker exec faq_rag_llm_bot-backend-1 python -m pytest tests/test_eval_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'eval_config'`.

- [ ] **Step 3: Написать `eval_config.py`**

`backend/scripts/eval_config.py`:
```python
"""Чистые (без тяжёлых импортов) хелперы для eval_rag.py — вынесены сюда,
чтобы покрыть юнит-тестами без загрузки mlflow/ragas/llama_index."""


def model_short(model: str) -> str:
    """Короткий слаг модели для run_name и имени кэша: последний сегмент после '/'.

    'deepseek/deepseek-v4-flash' -> 'deepseek-v4-flash'
    'qwen3:1.7b'                 -> 'qwen3:1.7b'
    """
    return model.split("/")[-1]


def samples_cache_filename(
    dataset_source: str, retrieval_mode: str, gen_short: str, top_k: int
) -> str:
    """Имя файла кэша RAG-ответов.

    Ключ включает генератор и top_k — иначе прогоны разных моделей на одном
    (source, mode) затирают друг друга (баг B4: второй/третий генератор
    подхватывал ответы первого).
    """
    return f"samples_{dataset_source}_{retrieval_mode}_{gen_short}_k{top_k}.json"


def build_mlflow_tags(
    *, git_commit, dataset_version, judge_model, purpose, stage, langfuse_session_id
) -> dict:
    """Теги MLflow для фильтрации/воспроизводимости (скилл tracking-experiments)."""
    return {
        "git_commit": git_commit,
        "dataset_version": dataset_version,
        "judge": judge_model,
        "purpose": purpose,
        "stage": stage,
        "langfuse_session_id": langfuse_session_id,
    }
```

- [ ] **Step 4: Запустить тест — убедиться, что проходит**

Run: `docker exec faq_rag_llm_bot-backend-1 python -m pytest tests/test_eval_config.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Подключить фикс ключа кэша в `eval_rag.py`**

В `eval_rag.py` после блока импортов из `app.core...` добавить (рядом с `from _hybrid_retriever` тоже используется path insert, здесь — свой):
```python
sys.path.insert(0, "/app/scripts")
from eval_config import build_mlflow_tags, model_short, samples_cache_filename
```

Заменить блок кэш-пути (строки ~382-384):
```python
    samples_cache_path = Path(
        f"/app/tests/eval/samples_{DATASET_SOURCE}_{RETRIEVAL_MODE}.json"
    )
```
на (вычисляем `gen_short` ЗДЕСЬ — выше по коду, чем сейчас на ~460):
```python
    gen_short = model_short(
        OPENROUTER_GEN_MODEL if GENERATOR_PROVIDER == "openrouter" else OLLAMA_GEN_MODEL
    )
    samples_cache_path = Path(
        "/app/tests/eval/"
        + samples_cache_filename(DATASET_SOURCE, RETRIEVAL_MODE, gen_short, TOP_K)
    )
```

Удалить теперь-дублирующее вычисление `gen_short` ниже (строки ~460-464):
```python
    gen_short = (
        OPENROUTER_GEN_MODEL.split("/")[-1]
        if GENERATOR_PROVIDER == "openrouter"
        else OLLAMA_GEN_MODEL
    )
```
(значение уже посчитано выше; `run_name` ниже переписывается в Task 2, `gen_short` там остаётся валиден.)

- [ ] **Step 6: Убедиться, что скрипт импортируется без ошибок**

Run: `docker exec faq_rag_llm_bot-backend-1 python -c "import sys; sys.argv=['x']; import ast; ast.parse(open('/app/scripts/eval_rag.py').read()); print('OK')"`
Expected: `OK` (синтаксис валиден; полный импорт тянет тяжёлые зависимости — достаточно ast-парса).

- [ ] **Step 7: Прогнать весь тест-набор — ничего не сломали**

Run: `docker exec faq_rag_llm_bot-backend-1 python -m pytest -q`
Expected: все прежние тесты + 4 новых PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/scripts/eval_config.py backend/tests/test_eval_config.py backend/scripts/eval_rag.py
git commit -m "fix(eval): ключ кэша RAG-ответов включает генератор+top_k (баг B4)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: MLflow-гигиена + env-driven параметры + latency

**Files:**
- Modify: `backend/scripts/eval_rag.py` — env-чтение `TOP_K`/`temperature`/эксперимента; короткий `run_name`; `set_tags`; `mean_latency_s`.

**Interfaces:**
- Consumes: `model_short`, `build_mlflow_tags` (Task 1).
- Produces: MLflow-раны с короткими именами, тегами `git_commit/dataset_version/judge/purpose/stage/langfuse_session_id`, метрикой `mean_latency_s`.

- [ ] **Step 1: `TOP_K` и `temperature` — из env**

В `eval_rag.py` заменить хардкод (строка ~84):
```python
TOP_K = 5
```
на:
```python
TOP_K = int(os.environ.get("RAG_TOP_K", "5"))
RAG_TEMPERATURE = float(os.environ.get("RAG_TEMPERATURE", "0.1"))
```

В `make_rag_llm()` заменить оба `temperature=0.1` на `temperature=RAG_TEMPERATURE`
(ветки ollama ~строка 292 и openrouter ~строка 312).

- [ ] **Step 2: Имя эксперимента — из env**

Заменить (строка ~453):
```python
    mlflow.set_experiment("ragas-eval")
```
на:
```python
    mlflow.set_experiment(os.environ.get("MLFLOW_EXPERIMENT", "ragas-eval"))
```

- [ ] **Step 3: Короткий `run_name`**

Заменить (строки ~465):
```python
    run_name = f"{DATASET_SOURCE}-{RETRIEVAL_MODE}-{gen_short}-judge-{judge_short}-k{TOP_K}"
```
на:
```python
    run_name = gen_short  # различитель — только модель; детали в params/tags
```
(`judge_short` больше не нужен для имени; если он использовался только здесь — удалить его вычисление на ~455-459.)

- [ ] **Step 4: Замер latency в RAG-цикле**

В свежей ветке генерации (не из кэша, ~строки 397-433) завести список и замер.
Добавить `import time` в шапку (если нет). Рядом с `samples = []`:
```python
        latencies = []
```
Обернуть вызов `run_rag`:
```python
                try:
                    _t0 = time.perf_counter()
                    answer, contexts = run_rag(item["question"], retriever, rag_llm)
                    latencies.append(time.perf_counter() - _t0)
                except Exception as e:
                    print(f"      [!] FAIL: {type(e).__name__}: {str(e)[:120]}")
                    failed_indices.append(i)
                    answer = "[Ошибка генерации: вопрос не отвечен]"
                    contexts = []
                    latencies.append(float("nan"))
```
Сохранять `latencies` в кэш (в `json.dump({...})`, ~строка 442):
```python
                {"samples": samples, "synthesizers": synthesizers, "latencies": latencies},
```
В кэш-ветке (~строка 389-393) поднять из файла:
```python
        latencies = cached.get("latencies", [])
```

- [ ] **Step 5: Логировать теги и `mean_latency_s`**

Сразу после `mlflow.log_params({...})` (после строки ~489) добавить:
```python
        mlflow.set_tags(
            build_mlflow_tags(
                git_commit=GIT_COMMIT,
                dataset_version=os.environ.get("DATASET_VERSION", "unknown"),
                judge_model=judge_model_name,
                purpose=os.environ.get("EVAL_PURPOSE", ""),
                stage=os.environ.get("EVAL_STAGE", ""),
                langfuse_session_id=lf_session_id,
            )
        )
```
После блока логирования метрик по колонкам (после строки ~525) добавить:
```python
        import math

        valid_lat = [x for x in latencies if isinstance(x, float) and not math.isnan(x)]
        if valid_lat:
            mlflow.log_metric("mean_latency_s", sum(valid_lat) / len(valid_lat))
```

- [ ] **Step 6: Синтаксис валиден**

Run: `docker exec faq_rag_llm_bot-backend-1 python -c "import ast; ast.parse(open('/app/scripts/eval_rag.py').read()); print('OK')"`
Expected: `OK`.

- [ ] **Step 7: Тест-набор зелёный**

Run: `docker exec faq_rag_llm_bot-backend-1 python -m pytest -q`
Expected: всё PASS (юнит-тесты `eval_config` не зависят от правок `main()`).

- [ ] **Step 8: Commit**

```bash
git add backend/scripts/eval_rag.py
git commit -m "feat(eval): env-driven top_k/temperature/experiment, короткий run_name, MLflow-теги + mean_latency_s

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Makefile `b4-stage1`, пред-флайт, прогон и фиксация прод-конфига

**Files:**
- Modify: `Makefile` — target `b4-stage1`.
- Modify: `PROJECT_STATUS.md` — итог B4.

**Interfaces:**
- Consumes: `make eval-golden` (существует), env `MLFLOW_EXPERIMENT/DATASET_VERSION/EVAL_PURPOSE/EVAL_STAGE/GEN_MODEL` из Task 2.

- [ ] **Step 1: Добавить target `b4-stage1` в Makefile**

После цели `eval-golden` (строка ~98) добавить (и внести `b4-stage1` в `.PHONY`):
```makefile
B4_GENERATORS = qwen/qwen3.6-plus deepseek/deepseek-v4-flash google/gemini-3.1-flash
B4_ENV = -e MLFLOW_EXPERIMENT=b4-generator-selection -e DATASET_VERSION=golden_v1 \
	-e EVAL_PURPOSE=b4-generator-selection -e EVAL_STAGE=1 \
	-e DATASET_PATH=/app/tests/eval/testset_golden.json

b4-stage1: ## B4 Этап 1 — прогнать 3 генератора-кандидата на golden (судья gpt-5.4)
	@for m in $(B4_GENERATORS); do \
	  echo ">> B4 generator: $$m"; \
	  docker exec $(EVAL_ENV) $(B4_ENV) -e OPENROUTER_GEN_MODEL="$$m" \
	    $(BACKEND) python -u scripts/eval_rag.py || exit 1; \
	done
	@echo ">> Готово. MLflow UI: make mlflow-ui → эксперимент b4-generator-selection"
```
Примечание: `EVAL_ENV` уже пробрасывает `OPENROUTER_GEN_MODEL="$(GEN_MODEL)"`; более поздний `-e OPENROUTER_GEN_MODEL="$$m"` в той же `docker exec` перебивает его (последний выигрывает).

- [ ] **Step 2: Проверить, что target виден и раскрывается**

Run: `make -n b4-stage1`
Expected: печатает три `docker exec ... OPENROUTER_GEN_MODEL="qwen/qwen3.6-plus" ...` / `deepseek/...` / `google/...` без ошибок раскрытия.

- [ ] **Step 3: ПРЕД-ФЛАЙТ (до трат) — ключ, Langfuse, смоук на 1 вопросе**

```bash
# ключ есть?
grep -q '^OPENROUTER_API_KEY=' .env.eval && echo "key OK"
# Langfuse поднят (A3, cost-трекинг)?
make langfuse-up
# смоук: 1 генератор, только импорт+генерация 1 вопроса не гоняем отдельно —
# вместо этого запускаем ОДНУ модель через eval-golden и смотрим, что ран создался.
docker exec $(EVAL_ENV) -e MLFLOW_EXPERIMENT=b4-smoke -e DATASET_VERSION=golden_v1 \
  -e EVAL_PURPOSE=smoke -e EVAL_STAGE=0 \
  -e DATASET_PATH=/app/tests/eval/testset_golden.json \
  -e OPENROUTER_GEN_MODEL=deepseek/deepseek-v4-flash \
  faq_rag_llm_bot-backend-1 python -u scripts/eval_rag.py
```
Expected: смоук-ран проходит без падений, в конце печатает `MLflow run_id`, метрики ненулевые. Если падает — чиним ДО полного прогона (бюджет не жжём).

- [ ] **Step 4: Полный прогон Этапа 1 (~$2.1 судьи)**

Run: `make b4-stage1 LANGFUSE_ENABLED=true`
Expected: 3 рана в эксперименте `b4-generator-selection`, у каждого CSV-артефакт, метрики `mean_faithfulness/answer_relevancy/context_precision/recall/latency_s`.

- [ ] **Step 5: Проверить чистоту сравнения + собрать числа**

```bash
make mlflow-ui   # http://localhost:5050
```
Проверить в Compare (3 рана):
- `mean_context_precision` и `mean_context_recall` ~равны у всех трёх (retrieval один → подтверждает валидность сравнения генераторов);
- разброс по `mean_faithfulness` / `mean_answer_relevancy` / `mean_latency_s`.
Cost — в Langfuse (http://localhost:3001) по `langfuse_session_id` каждого рана.

- [ ] **Step 6: Ручная проверка русского (тай-брейк) на топ-2**

Открыть CSV-артефакты топ-2 кандидатов, глазами прочитать ответы на юр-терминологию ФПСР (11 вопросов). Зафиксировать вывод: у кого русский/термины чище.

- [ ] **Step 7: Записать вывод в `note` ранов**

Для каждого рана в MLflow UI → вкладка → Description, либо программно:
```bash
docker exec faq_rag_llm_bot-backend-1 python -c "
import mlflow
mlflow.set_tracking_uri('sqlite:////app/mlflow.db')
# run_id взять из UI/вывода прогона
mlflow.tracking.MlflowClient().set_tag('<RUN_ID>', 'mlflow.note.content', '<вывод>')
"
```
(указать реальные run_id и текст вывода по итогам Step 5-6).

- [ ] **Step 8: Зафиксировать прод-генератор в PROJECT_STATUS.md**

- Отметить `[x] B4` (или частично — Этап 1) в «Открытые задачи».
- Если победитель ≠ `qwen/qwen3.6-plus` — обновить строку RAG-генератора в таблице моделей + `GEN_MODEL` в `backend/models.env`.
- Добавить строку в «Хронологию» с датой 2026-07-19 и однострочным выводом.

- [ ] **Step 9: Commit**

```bash
git add Makefile PROJECT_STATUS.md backend/models.env
git commit -m "feat(eval): B4 Этап 1 — target b4-stage1 + доказательный выбор прод-генератора

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Кандидаты 3 облачных → Task 3 `B4_GENERATORS`. ✅
- Фикс кэша (модель+top_k) → Task 1. ✅
- Короткий run_name + теги + latency, cost только в Langfuse → Task 2 (latency-метрика; cost не логируется в MLflow — `langfuse_session_id` в тегах даёт связь). ✅
- Эксперимент `b4-generator-selection`, dataset_version=golden_v1, judge-тег → Task 2/3. ✅
- Правило quality-gate + дешёвый + ручной русский → Task 3 Step 5-6. ✅
- Этапы 2/3 вне объёма → `RAG_TOP_K` env готов под Этап 2 без правок кода. ✅
- Пред-флайт перед тратами → Task 3 Step 3. ✅

**Placeholder scan:** В Task 3 Step 7 `<RUN_ID>`/`<вывод>` — не плейсхолдеры плана, а обязательные runtime-значения (известны только после прогона); это отмечено явно. Остальной код — полный.

**Type consistency:** `model_short`/`samples_cache_filename`/`build_mlflow_tags` определены в Task 1 и используются с теми же сигнатурами в Task 1 Step 5 и Task 2 Step 5. `gen_short` вычисляется один раз (Task 1 Step 5), переиспользуется в `run_name` (Task 2 Step 3). ✅
