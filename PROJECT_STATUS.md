# 📊 PROJECT STATUS — единая точка правды

> **Это главный файл статуса проекта.** Открывай его первым в начале каждой сессии.
> Здесь: хронология разработки + все открытые задачи + ссылки на детальные документы.
> Обновляй в конце каждой сессии (строка в «Хронологию» + галочки в «Открытых задачах»).

**Проект:** FAQ RAG Bot — ответы на вопросы по документам компании (ФПСР).
**Репозиторий:** https://github.com/GachiB0y/FAQ_RAG_llm_bot

---

## 🎯 ТЕКУЩИЙ ФОКУС

**MLOps-практики** — превращаем «набор скриптов» в воспроизводимый pipeline.
Сделано: A1 (uv) ✅, A2 (Makefile) ✅. Следующее действие: **A3 (Langfuse)** или **A6 (Prefect)**.
Детальный трекер: [docs/plans/2026-07-06-mlops-implementation-status.md](docs/plans/2026-07-06-mlops-implementation-status.md)

---

## ⬜ ОТКРЫТЫЕ ЗАДАЧИ

### Линия A — MLOps-практики (приоритет) ⭐
Лечим «7 болей ML». Анализ: [mlops-maturity-analysis](docs/plans/2026-07-06-mlops-maturity-analysis.md)
- [x] **A1** `uv` + lockfile (боль #5 — окружение) ✅ 2026-07-08
- [x] **A2** Makefile ✅ 2026-07-08 — (боль #1 — ручной труд)
- [ ] **A3** Langfuse — мониторинг запросов (боль #4) ⭐
- [ ] **A4** DVC — версионирование данных/промптов (боль #2)
- [ ] **A5** CI с Ragas — тесты качества в PR (боли #7, #3)
- [ ] **A6** Prefect — оркестрация: retry на 429 + nightly eval (после A2). Интро: [prefect-intro](docs/plans/2026-07-06-prefect-intro.md)

### Линия B — Production-архитектура
Роадмап: [production-tooling-roadmap](docs/plans/2026-07-02-production-tooling-roadmap.md)
- [ ] **B1** vLLM — прод-инференс вместо Ollama
- [ ] **B2** LangGraph — agentic RAG (главный тренд 2026)
- [ ] **B3** pgvector — проверить, нужна ли отдельная векторка

### Линия C — Отложенное из первоначального плана
- [ ] **C1** MLflow как сервис в docker-compose (частично закрывается линией A)
- [ ] **C2** Prefect + загрузка полного корпуса с Яндекс-Диска (отложено)

### Линия D — По желанию
- [ ] **D1** Калькулятор затрат на токены (`cost-estimation.md`), заготовка есть:
      `backend/scripts/_count_tokens.py`

---

## ✅ СДЕЛАНО (хронология разработки)

### Раньше (git-история до 2026-06)
- Backend (FastAPI + LlamaIndex + Qdrant), Frontend (React FSD), auth-fix,
  chat-history, production-infra design — см. `docs/plans/2026-02-*` и `2026-03-*`.

### Сессии июнь-июль 2026 (Ragas + MLflow + MLOps)

| Дата | Что сделано | Документы |
|---|---|---|
| 28.06 | Изучили Ragas + MLflow. Учебный eval-скрипт. Эксперимент №1 (dense vs hybrid) — hybrid «выиграл» +21..51% | [eval-status](docs/plans/2026-06-28-ragas-mlflow-eval-status.md), [workflow-гайд](docs/plans/2026-06-28-ragas-full-workflow.md) |
| 29.06 | Отчёт и презентация по эксп.1. Залили проект на GitHub (public, README, notebook) | [experiment-report](docs/plans/2026-06-29-ragas-experiment-report.md), [slides](docs/plans/2026-06-29-ragas-experiment-slides.html) |
| 30.06 | **Эксперимент №2 (чистый):** независимый судья (gpt-oss-120b) + OCR картинки + testset на 3 документа. **Вывод: hybrid НЕ помогает** — эксп.1 был искажён self-bias судьи. Урок: методология eval критичнее оптимизации | [clean-experiment-report](docs/plans/2026-06-30-clean-experiment-report.md) |
| 30.06 | Графики matplotlib в отчёт, Jupyter notebook для анализа, CSV-снепшоты в репо | [notebook](notebooks/01_experiment_analysis.ipynb) |
| 02.07 | Роадмап production-инструментов 2026 (vLLM, LangGraph, pgvector, Langfuse) | [production-tooling-roadmap](docs/plans/2026-07-02-production-tooling-roadmap.md) |
| 06.07 | Анализ MLOps-зрелости (7 болей) + пошаговый трекер внедрения (uv→Makefile→Langfuse→DVC→CI). Вводные доки по uv/Makefile/Prefect. Скилл `tracking-experiments-with-mlflow` | [mlops-maturity-analysis](docs/plans/2026-07-06-mlops-maturity-analysis.md), [mlops-implementation-status](docs/plans/2026-07-06-mlops-implementation-status.md) |
| 08.07 | **A1 (uv)**: pyproject+eval-группа, uv.lock (214 пакетов), Dockerfile на `uv sync`, OCR в образ, venv→/opt/venv (фикс bind-mount). **A2 (Makefile)**: весь пайплайн через `make <target>` | [mlops-implementation-status](docs/plans/2026-07-06-mlops-implementation-status.md) |

**Ключевой результат экспериментов:** на нашем корпусе (bge-m3 + документы ФПСР)
hybrid search **не даёт значимого преимущества** — dense достаточен. Главный урок —
про важность корректной методологии оценки (независимый судья, чистый корпус,
разнообразный testset).

---

## 🗺 КАРТА ДОКУМЕНТОВ

| Документ | О чём |
|---|---|
| **PROJECT_STATUS.md** (этот файл) | 📊 Главный трекер — открывай первым |
| `docs/plans/2026-07-06-mlops-implementation-status.md` | Детальный трекер MLOps (шаги A1-A5) |
| `docs/plans/2026-07-06-mlops-maturity-analysis.md` | Анализ 7 болей ML |
| `docs/plans/2026-07-02-production-tooling-roadmap.md` | vLLM / LangGraph / pgvector / Langfuse |
| `docs/plans/2026-06-30-clean-experiment-report.md` | Финальный отчёт эксперимента (dense vs hybrid) |
| `docs/plans/2026-06-29-ragas-experiment-report.md` | Отчёт первого (искажённого) эксперимента |
| `docs/plans/2026-06-28-ragas-full-workflow.md` | Теория Ragas (KG, personas, метрики) |
| `notebooks/01_experiment_analysis.ipynb` | Интерактивный анализ результатов |
| `README.md` | Обзор проекта, quick start |

---

## 📝 ПРАВИЛА ВЕДЕНИЯ ЭТОГО ФАЙЛА

1. **Начало сессии:** читаем «Текущий фокус» и «Открытые задачи».
2. **Конец сессии:** ставим `[x]` на сделанное, добавляем строку в «Хронологию».
3. Новая крупная линия работ → новый пункт в «Открытые задачи» + детальный
   документ в `docs/plans/` со ссылкой отсюда.
4. Детали живут в дат-документах, здесь — только сводка и указатели.
