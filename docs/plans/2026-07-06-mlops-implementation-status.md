# MLOps-внедрение: статус выполнения (живой трекер)

**Создан:** 2026-07-06
**Назначение:** пошагово внедряем MLOps-практики, лечим «7 болей». Этот файл —
единая точка правды между сессиями: где мы сейчас, что дальше. Отмечаем `[x]`
по мере выполнения.

**Анализ болей:** см. [2026-07-06-mlops-maturity-analysis.md](2026-07-06-mlops-maturity-analysis.md)

---

## 📍 YOU ARE HERE

> **Текущий шаг:** ✅ Шаги A (uv) + B (Makefile) + C (Langfuse) готовы. Следующее —
> **Шаг D (DVC)** или **Шаг F (Prefect)**. Обнови этот блок в конце каждой сессии.

**Лог сессий:**
- 2026-07-15/16: **Шаг C (Langfuse) сделан.** Self-hosted v3 (`make langfuse-up`, :3001),
  модуль `observability.py` (оба контура eval+live, флаг `LANGFUSE_ENABLED`), генератор
  через OpenInference (langfuse.llama_index в v3 удалён), судья через LangChain-callback,
  Ragas-метрики как Scores, custom-прайсинг скриптом (`make langfuse-prices`). Сверка cost
  Langfuse↔OpenRouter ~4%. Попутно залечена боль #5 (llama-index-llms-openai-like в lock),
  генератор qwen/qwen3.6→qwen/qwen3.6-plus (голого слага на OR нет).
- 2026-07-06: создан план + вводные доки (uv, Makefile, Prefect intro). Решили
  идти по порядку A→B→F.
- 2026-07-08: **Шаг A (uv) сделан.** pyproject + группа eval с пинами, uv.lock
  (214 пакетов), Dockerfile на `uv sync`, OCR-пакеты запечены в образ. Поймали и
  починили баг: bind-mount ./backend:/app прятал /app/.venv → вынесли venv в
  /opt/venv. Eval-стек работает из коробки без ручных pip install.
- 2026-07-08: **Шаг B (Makefile) сделан.** Все docker exec простыни → цели
  (make corpus/ingest/ocr/kg/testset/eval-dense/eval-hybrid/mlflow-ui). Ключ из
  .env.eval, модели через переменные, `make help` самодокументируется. Дальше — Langfuse или Prefect.

---

## Порядок шагов (по нарастающей)

### ✅ Шаг A — `uv` + lockfile (лечит боль #5 «бардак в окружении») — СДЕЛАНО

📖 Вводная: [uv-intro](2026-07-06-uv-intro.md)

- [x] Установлен `uv` 0.11.28 (на хосте через brew)
- [x] `uv.lock` (214 пакетов, пины зафиксированы навсегда)
- [x] eval-зависимости в группе `[dependency-groups] eval` (ragas==0.2.15,
      langchain<0.4, mlflow, fastembed, tiktoken, rapidfuzz, pymupdf, matplotlib, pandas)
- [x] Dockerfile на `uv sync --frozen --group eval` + OCR-пакеты в образ (tesseract-rus, poppler)
- [x] Проверено: пересборка → eval-стек из коробки, без ручных `pip install`

**Урок:** bind-mount `./backend:/app` прятал `/app/.venv` → вынесли venv в
`/opt/venv` через `UV_PROJECT_ENVIRONMENT`.

---

### ✅ Шаг B — Makefile (лечит боль #1 «ручной труд») — СДЕЛАНО

📖 Вводная: [makefile-intro](2026-07-06-makefile-intro.md)

- [x] up/down/rebuild/logs/shell — инфраструктура
- [x] corpus — копирование тестовых доков в контейнер (был ручной docker cp)
- [x] ingest / ingest-hybrid / ocr — данные
- [x] kg / testset / eval-dense / eval-hybrid — Ragas pipeline
- [x] mlflow-ui / mlflow-stop — UI
- [x] Ключ OpenRouter из `.env.eval` (не хардкод), модели через переменные
- [x] `make help` — самодокументация
- [x] Проверено: `make help`, `make -n ingest`, `make corpus` реально работают

**Готово:** весь пайплайн через `make <target>` вместо копипасты docker-команд.

---

### ✅ Шаг C — Langfuse (лечит боль #4 «нет мониторинга») — СДЕЛАНО 2026-07-16

Реализация: [langfuse-observability plan](../superpowers/plans/2026-07-15-langfuse-observability.md).
Кратко: self-hosted v3 (:3001), `observability.py` (флаг-gated, оба контура), генератор
через OpenInference, судья через LangChain-callback, Ragas→Scores, custom-прайсинг скриптом,
сверка cost с OpenRouter ~4%. Ниже — исходный чек-лист (выполнен):


📖 **Вводная перед реализацией:** [langfuse-intro](2026-07-08-langfuse-intro.md)

Self-hosted трейсинг каждого LLM-запроса.

- [ ] Добавить Langfuse-сервисы в отдельный `docker-compose.langfuse.yml`
      (у них есть готовый compose)
- [ ] Обернуть `RAGEngine.query()` в `@observe()` / Langfuse-трейсинг
- [ ] **Прокидывать `user_id` в трейсы** — единый механизм:
      - в eval: `user_id` = персона/номер вопроса (тест-данные как на проде)
      - в проде (Telegram): `user_id` = telegram user id
      → тогда observability прод-подобна уже на тестах, и потом бесшовно в прод
- [ ] Проверить что цена OpenRouter-моделей распознаётся (иначе прописать вручную,
      чтобы $/запрос считался верно)
- [ ] Сделать 5-10 запросов → увидеть трейсы (retrieval + generation по шагам)
- [ ] Посмотреть latency-разбивку и стоимость запросов ($, токены)
- [ ] (опц.) online-eval: Langfuse прогоняет faithfulness на семпле
- [ ] Сравнить UX с MLflow — что для чего

**Готово когда:** в Langfuse UI видны реальные запросы к чату с разбивкой шагов,
latency и стоимости.

---

### ⬜ Шаг D — DVC (лечит боль #2 «не версионируется»)

Версионирование данных/артефактов, привязанное к git-коммиту.

- [ ] `dvc init`
- [ ] Взять под DVC: `kg.json`, `testset_auto.json`, eval-CSV, embeddings
- [ ] Настроить remote (локальный или S3/MinIO — у нас MinIO есть в окружении)
- [ ] Вынести `SYSTEM_PROMPT` из кода → версионируемый файл промпта
- [ ] Проверить: `git checkout <старый коммит>` + `dvc checkout` → те же данные
- [ ] (опц.) `dvc.yaml` pipeline — ingest→kg→testset→eval как DVC-стадии

**Готово когда:** по git-коммиту однозначно восстанавливается «эти данные + этот
промпт + эта модель = эти метрики».

---

### ⬜ Шаг E — CI с Ragas (лечит боли #7 «тестирование» + #3 «ML/Ops»)

GitHub Actions: при PR гоняет pytest + mini eval, краснеет при регрессии метрик.

- [ ] `.github/workflows/ci.yml`: линт (ruff) + pytest (loader/auth)
- [ ] Отдельный job: mini eval-прогон (3-5 вопросов, дешёвый судья)
- [ ] Порог: fail если `mean_faithfulness` < X (например 0.7)
- [ ] Секрет `OPENROUTER_API_KEY` в GitHub Secrets (не в репо)
- [ ] Badge статуса CI в README

**Готово когда:** PR автоматически проверяется — и код (pytest), и качество RAG
(Ragas), красный при просадке.

---

### ⬜ Шаг F — Prefect (оркестрация: retry + расписание) — лечит боль #1 глубже

Обернуть пайплайн ingest→kg→testset→eval в Prefect flow. Главная польза для нас —
**автоматический retry на 429 от OpenRouter** (мы мучились ручными рестартами) +
запуск eval по расписанию (nightly).

Вводный документ (читать перед реализацией):
[prefect-intro](2026-07-06-prefect-intro.md)

- [ ] Установить `prefect` (через uv-группу eval)
- [ ] Обернуть шаги пайплайна в `@task` (ingest, build_kg, gen_testset, run_eval)
- [ ] `@task(retries=5, retry_delay_seconds=60)` на eval — авто-повтор при 429
- [ ] Собрать `@flow` с правильным порядком зависимостей
- [ ] Поднять Prefect UI (docker или локально) → посмотреть граф прогона
- [ ] (опц.) Deployment с расписанием — nightly eval

**Готово когда:** `prefect deployment run` гоняет весь пайплайн, сам ретраит
упавшие на 429 шаги, а в UI виден граф и статус каждого шага.
**Порядок:** ПОСЛЕ Шага B (Makefile). Prefect — поверх, не вместо.

---

## Что НЕ делаем в этой итерации (осознанно отложено)

- Dagster — Prefect (Шаг F) покрывает нашу потребность в оркестрации
- Kubernetes/Helm — избыточно для pet-проекта
- Terraform/IaC — нет облака пока
- Evidently (drift-мониторинг) — после Langfuse, когда будет поток запросов
- vLLM, LangGraph, pgvector — это [production-tooling-roadmap](2026-07-02-production-tooling-roadmap.md),
  отдельная линия (про архитектуру, не про MLOps-процесс)

---

## Связь с другими документами

- **Боли и обоснование:** [2026-07-06-mlops-maturity-analysis.md](2026-07-06-mlops-maturity-analysis.md)
- **Прод-архитектура (vLLM/LangGraph/pgvector):** [2026-07-02-production-tooling-roadmap.md](2026-07-02-production-tooling-roadmap.md)
- **Затраты на токены:** обсуждалось в чате (можно оформить в `cost-estimation.md`)
- **Результаты экспериментов:** [2026-06-30-clean-experiment-report.md](2026-06-30-clean-experiment-report.md)
