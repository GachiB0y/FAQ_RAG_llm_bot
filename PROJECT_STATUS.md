# 📊 PROJECT STATUS — единая точка правды

> **Это главный файл статуса проекта.** Открывай его первым в начале каждой сессии.
> Здесь: хронология разработки + все открытые задачи + ссылки на детальные документы.
> Обновляй в конце каждой сессии (строка в «Хронологию» + галочки в «Открытых задачах»).

**Проект:** FAQ RAG Bot — ответы на вопросы по документам компании (ФПСР).
**Репозиторий:** https://github.com/GachiB0y/FAQ_RAG_llm_bot

---

## 🎯 ТЕКУЩИЙ ФОКУС

**Пивот на линию E — демо для коллег** (после закрытия A3 Langfuse ✅).
MLOps-костяк готов: A1 (uv) ✅, A2 (Makefile) ✅, A3 (Langfuse) ✅. A4 (DVC)/A6 (Prefect) — отложены.
**Следующее действие: E4 (Security Gateway)** — спека готова → writing-plans/TDD.
Согласованный план демо — см. блок «Линия E» ниже (2026-07-16).
Трекеры: [MLOps](docs/plans/2026-07-06-mlops-implementation-status.md) · [A3-план](docs/superpowers/plans/2026-07-15-langfuse-observability.md)

---

## 🤖 МОДЕЛИ ПРОЕКТА (текущий набор)

Платный cost/quality набор через OpenRouter (3 разные семьи, судья независим от
генератора → нет self-preference bias). Всё через один ключ OpenRouter — ключ
Anthropic не нужен. Обновлено 2026-07-10 (свежие модели на июль 2026).
Обоснование + цены: [model-flow](docs/plans/2026-07-08-model-flow.md).
**Единый источник имён моделей — `backend/models.env`** (Makefile его `include`-ит,
скрипты получают через env и своих дефолтов не имеют). Прод-openai-путь — в `Settings.RAG_GENERATOR_MODEL`.

| Роль | Модель | Семья | Где | Цена $/1M (in/out) |
|---|---|---|---|---|
| RAG-генератор (отвечает юзерам, в прод) | `qwen/qwen3.6-plus` ¹ | Alibaba (кит.) | OpenRouter | 0.33 / 1.95 |
| Судья (eval) | `openai/gpt-5.4` (полная, не mini!) | OpenAI | OpenRouter | 2.50 / 15 |
| KG + testset | `google/gemini-3.1-flash-lite` | Google | OpenRouter | 0.25 / 1.50 |
| Эмбеддинги | `bge-m3` | — | локально (Ollama) | — |
| OCR | Tesseract | — | локально | — |

> ¹ Генератор `qwen/qwen3.6-plus` — хороший русский (201 язык). Точный слаг уточнён
> 2026-07-16: голого `qwen/qwen3.6` на OpenRouter нет, взят `-plus` ($0.33/$1.95).
> Дешёвая альтернатива — `deepseek/deepseek-v4-flash`
> (~0.14/0.28), но русский слабее → **прогнать 10–15 вопросов ФПСР глазами до фиксации**.
> Если русский «плывёт» на юр-терминологии — fallback генератор `google/gemini-3.1-flash`.
> Судья намеренно ПОЛНАЯ GPT (не mini): он определяет доверие к метрикам, гоняется только
> на eval (объём мал → цена ~$1.3/прогон на 30 вопросах). Урок 30.06 про self-bias судьи.

> Генератор можно вынести в локальный контур (vLLM на GPU) сменой 2 строк конфига —
> см. model-flow §5.1. Архитектура готова (OpenAI-совместимый API).

---

## ⬜ ОТКРЫТЫЕ ЗАДАЧИ

### Линия A — MLOps-практики (приоритет) ⭐
Лечим «7 болей ML». Анализ: [mlops-maturity-analysis](docs/plans/2026-07-06-mlops-maturity-analysis.md)
- [x] **A1** `uv` + lockfile (боль #5 — окружение) ✅ 2026-07-08
- [x] **A2** Makefile ✅ 2026-07-08 — (боль #1 — ручной труд)
- [x] **A3** Langfuse — мониторинг запросов + фактическая стоимость токенов (боль #4) ✅ 2026-07-16
  - [x] **A3.1** Оба узла инструментированы: генератор (LlamaIndex через OpenInference) и судья
        (LangChain `ChatOpenAI` в Ragas через Langfuse callback). Модуль `observability.py`.
  - [x] **A3.2** Custom model prices заданы СКРИПТОМ (`make langfuse-prices`, не руками в UI):
        qwen/openai/google-слаги. Проверено: cost ненулевой.
  - [x] **A3.3** Сверено на прогоне 3 вопросов: Langfuse ~$0.184 vs OpenRouter $0.177 (~4%,
        разница custom-цены vs факт-биллинг). Судья = ~95% стоимости — подтверждено.
  - [x] (следствие) `user_id` в трейсах (eval:персона / telegram id в live) → фундамент под E1
  - Реализация: self-hosted Langfuse v3 (`make langfuse-up`, :3001), флаг `LANGFUSE_ENABLED`
- [ ] **A4** DVC — версионирование данных/промптов (боль #2)
- [ ] **A5** CI с Ragas — тесты качества в PR (боли #7, #3)
- [ ] **A6** Prefect — оркестрация: retry на 429 + nightly eval (после A2). Интро: [prefect-intro](docs/plans/2026-07-06-prefect-intro.md)

### Линия B — Production-архитектура
Роадмап: [production-tooling-roadmap](docs/plans/2026-07-02-production-tooling-roadmap.md)
- [ ] **B1** vLLM — прод-инференс вместо Ollama
- [ ] **B2** LangGraph — agentic RAG (главный тренд 2026)
- [ ] **B3** pgvector — проверить, нужна ли отдельная векторка
- [ ] **B4** 🎯 Доказать выбор прод-генератора на данных: гоняем `qwen/qwen3.6-plus`
      (текущий выбор) против кандидатов — `deepseek/deepseek-v4-flash` (дешевле),
      `google/gemini-3.1-flash` (fallback), локальная модель через vLLM/Ollama —
      на ОДНОМ testset через Ragas+MLflow, судья `openai/gpt-5.4`. Убедиться что
      выбор лучший по цена/качество (в т.ч. русский на юр-терминологии ФПСР). Плюс
      поиграться с параметрами: `top_k`/`temperature`/`prompt` (query-time), `chunk_size`
      (index-time → переиндексация) → зафиксировать прод-конфиг с доказательством в MLflow.
      **Курированный golden-testset готов:** `backend/tests/eval/testset_golden.json`
      (11 вопросов, все 3 документа) → `make eval-golden` (~$0.7/прогон судьи). Факт-cost — в Langfuse (A3).
- [ ] **B5** (опц., прод) **Promptfoo** — стенд для red-team / prompt-injection тестов:
      прогнать пачку атак против бота и проверить, что guard из **E4** их ловит. Плюс
      быстрые side-by-side сравнения промптов/моделей (частично пересекается с B4).
      Наш eval-стек (Ragas+MLflow+Langfuse) это не покрывает — Promptfoo добавляет
      именно security-тестирование. Для демо не нужен, кандидат в прод.

### Линия C — Отложенное из первоначального плана
- [ ] **C1** MLflow как сервис в docker-compose (частично закрывается линией A)
- [ ] **C2** Prefect + загрузка полного корпуса с Яндекс-Диска (отложено)

### Линия D — По желанию
- [ ] **D1** Калькулятор затрат на токены (`cost-estimation.md`), заготовка есть:
      `backend/scripts/_count_tokens.py`

### Линия E — Демо для коллег (Telegram-бот + презентация) 🎤
Цель: живой интерактив — коллеги задают вопросы боту в Telegram по документам ФПСР.

**📋 Согласованный план демо (2026-07-16). Формат: коллеги тыкают бота КАЖДЫЙ со своего Telegram (конкурентно, ~10 человек).**

Последовательность:
1. **E4 (Security Gateway)** — старт. Спека готова → writing-plans/TDD.
2. **Минимальный бот E1 — рано** (де-риск: демо-костяк обязан работать, хоть на текущем генераторе).
3. **B4** — прогон + сравнение в MLflow/Langfuse как демонстрация методологии тестирования.
4. **M1 (OpenRouter в live) + M2 (`run_in_threadpool`)** — качество + конкурентность (= линия E3).
5. **Живые крутилки** `top_k`/`threshold`/`temperature`/`prompt` в админке — демо-фича/эксплорейшн, если останется время.

Минимальный набор под демо (must-have): **M1 (OpenRouter-генератор в live) + M2 (threadpool) + M3 (=E1 бот) + M4 (=rate-limit, половина E4)**. Injection-guard (вторая половина E4), vLLM, B4 — сверх минимума.

Ключевые решения (обоснования — в истории 2026-07-16):
- **Архитектура:** монолит Python/FastAPI. Gateway = **in-process dependency** на `/api/v1/chat` перед `RAGEngine.query`, НЕ отдельный сервис (Go-gateway = оверинжиниринг для нашего масштаба). API и React-фронт/админка уже есть; бот — ещё один тонкий клиент той же апишки.
- **Конкурентность:** узкое место — **инференс модели**, не HTTP-слой. Решается генератором в OpenRouter (облако параллелит) + `run_in_threadpool` (сейчас `rag.query` синхронно блокирует event loop), а не языком API. vLLM (B1) — потом.
- **Параметры:** `top_k`/`threshold`/`temperature`/`prompt` = **query-time** → можно вживую (инфра `SystemSettings` есть, `RAGEngine` научить читать). `chunk_size`/`overlap` = **index-time** → только через переиндексацию корпуса, тестируются в **B4 офлайн**, крутилкой нельзя.
- **B4 = измеренный тюнинг (авторитет); живые крутилки = эксплорейшн на глаз, НЕ замена измерению** (урок 30.06 про self-bias). Здоровый цикл: покрутил живьём → гипотеза → доказал в B4 → зафиксировал.
- Бюджет демо: ~10 чел × 10 вопросов × ~$0.003 ≈ **$0.30**; rate-limit (E4) = потолок бюджета/нагрузки.

- [ ] **E1** Telegram-бот поверх нашего RAG (aiogram/python-telegram-bot):
      юзер пишет вопрос → бот отвечает через `RAGEngine.query()` + источники.
      `user_id` = telegram id → в Langfuse видно кто что спрашивал и почём.
      NB: `/api/v1/chat` сейчас требует JWT (`get_current_user`) → боту нужна
      сервис-аутентификация (бот-токен) + прокидывание telegram `user_id` в запрос
      (по нему же лимитит E4). Live-генератор — вкрутить OpenRouter (M1), сейчас Ollama.
- [ ] **E2** Презентация на основе 3 наших документов
      ([workflow](RAG_AGENT_WORKFLOW.md) + [эксперимент](docs/plans/2026-06-30-clean-experiment-report.md)
      + [MLOps-анализ](docs/plans/2026-07-06-mlops-maturity-analysis.md)) +
      живой интерактив: коллеги задают вопросы боту прямо на презентации
- [ ] **E3** стабильность под параллельными юзерами → решается **M1 (OpenRouter в live)
      + M2 (`run_in_threadpool`)** из плана демо выше (узкое место — инференс, не HTTP)
- [ ] **E4** 🔒 Security Gateway перед `RAGEngine.query` — первый user-facing контур
      закрываем защитным слоем из статьи об архитектуре AI-агентов. Дизайн утверждён,
      реализация позже: [security-gateway-design](docs/superpowers/specs/2026-07-14-security-gateway-design.md)
  - [ ] rate-limit 10 запросов/день на `user_id` (Redis) — защита бюджета/DoS ⭐ **минимум для демо (=M4)**
  - [ ] prompt-injection guard: правила (fast-path) + дешёвый LLM на спорных — витрина, опц. для демо
  - [ ] видимость: лог решений + `/api/v1/gateway/stats` (сколько атак отбито)
  - [ ] (прод-потом) allowlist / PII-маскирование / кэш / авто-фолбэк модели

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
| 14.07 | Разбор статьи «Архитектура надёжных AI-агентов» → gap-анализ проекта. Главный пробел — защитный слой **Gateway (безопасность)**. Спроектирован Security Gateway для демо-бота (rate-limit + injection-guard), спека утверждена → задача **E4** | [security-gateway-design](docs/superpowers/specs/2026-07-14-security-gateway-design.md) |
| 15-16.07 | **A3 (Langfuse) ✅** — self-hosted v3 (:3001), модуль `observability.py` (оба контура: eval + live, флаг-gated), генератор через OpenInference, судья через LangChain-callback, Ragas-метрики как Scores, custom-прайсинг скриптом (A3.2), сверка cost с OpenRouter ~4% (A3.3). Попутно: боль #5 — `llama-index-llms-openai-like` в lock; генератор `qwen/qwen3.6`→`qwen/qwen3.6-plus` | [langfuse-observability](docs/superpowers/plans/2026-07-15-langfuse-observability.md) |
| 16.07 | **Архитектурный анализ + план демо** (пивот на линию E). Разобрали слои (ядро/API/клиенты), место Gateway (in-process dependency, не Go-сервис), конкурентность (узкое место — инференс, решается OpenRouter-live + threadpool), query-time vs index-time параметры. Согласована последовательность демо: E4 → мин.бот → B4 → M1/M2 → крутилки | блок «Линия E» выше |
| 16.07 | **Курированный golden-testset** для B4/демо. Разобрали, что авто-testset из Ragas (персоны novice/instructor/lawyer → «странные» вопросы) имел дыры покрытия (нет «какие документы/как вступить», тонко по «Правилам»). Собрали `testset_golden.json`: 7 отобранных авто + 4 ручных (документы ЮЛ, шаги вступления, дисциплины, безопасность) = 11 вопросов, все 3 документа. Цель `make eval-golden` | `backend/tests/eval/testset_golden.json` |

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
