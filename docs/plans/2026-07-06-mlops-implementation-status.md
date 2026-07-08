# MLOps-внедрение: статус выполнения (живой трекер)

**Создан:** 2026-07-06
**Назначение:** пошагово внедряем MLOps-практики, лечим «7 болей». Этот файл —
единая точка правды между сессиями: где мы сейчас, что дальше. Отмечаем `[x]`
по мере выполнения.

**Анализ болей:** см. [2026-07-06-mlops-maturity-analysis.md](2026-07-06-mlops-maturity-analysis.md)

---

## 📍 YOU ARE HERE

> **Текущий шаг:** ✅ Шаг A (uv) готов. Следующее действие — **Шаг B (Makefile)**.
> Обнови этот блок в конце каждой сессии — одна строка «что сделано, что дальше».

**Лог сессий:**
- 2026-07-06: создан план + вводные доки (uv, Makefile, Prefect intro). Решили
  идти по порядку A→B→F.
- 2026-07-08: **Шаг A (uv) сделан.** pyproject + группа eval с пинами, uv.lock
  (214 пакетов), Dockerfile на `uv sync`, OCR-пакеты запечены в образ. Поймали и
  починили баг: bind-mount ./backend:/app прятал /app/.venv → вынесли venv в
  /opt/venv. Eval-стек работает из коробки без ручных pip install. Дальше — Makefile.

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

### ⬜ Шаг B — Makefile (лечит боль #1 «ручной труд»)

📖 **Вводная перед реализацией:** [makefile-intro](2026-07-06-makefile-intro.md)

Обернуть простыни `docker exec -e ... python scripts/...` в короткие команды.

- [ ] `make up` / `make down` — поднять/погасить стек
- [ ] `make ingest` — загрузка корпуса (dense)
- [ ] `make ingest-hybrid` — загрузка в hybrid-коллекцию
- [ ] `make ocr` — OCR картинок-PDF
- [ ] `make kg` — построить knowledge graph
- [ ] `make testset` — сгенерировать testset
- [ ] `make eval-dense` / `make eval-hybrid` — прогоны
- [ ] `make mlflow-ui` / `make jupyter` — поднять UI/notebook
- [ ] Ключ OpenRouter подхватывать из `.env.eval` внутри Makefile (не хардкодить)

**Готово когда:** весь пайплайн запускается через `make <target>`, а не копипастой
длинных docker-команд.

---

### ⬜ Шаг C — Langfuse (лечит боль #4 «нет мониторинга») ⭐

Self-hosted трейсинг каждого LLM-запроса.

- [ ] Добавить Langfuse-сервисы в отдельный `docker-compose.langfuse.yml`
      (у них есть готовый compose)
- [ ] Обернуть `RAGEngine.query()` в `@observe()` / Langfuse-трейсинг
- [ ] Сделать 5-10 запросов → увидеть трейсы (retrieval + generation по шагам)
- [ ] Посмотреть latency-разбивку и стоимость запросов
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
