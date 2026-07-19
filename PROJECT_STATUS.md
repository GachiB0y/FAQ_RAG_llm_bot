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
**E4 (Security Gateway) ✅** — закрыт. **M1 (OpenRouter в live) ✅** + **M2 (`run_in_threadpool`) ✅** — закрыты.
**B4 Этап 1 ✅** (2026-07-19) — прод-генератор доказательно сменён на `deepseek/deepseek-v4-flash`.
**Следующее действие: E1 (Telegram-бот)** (+ добавить B4-отчёт в презентацию E2). Опц.: B4 Этап 2 (`top_k`-свип).
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
| RAG-генератор (отвечает юзерам, в прод) | `deepseek/deepseek-v4-flash` ¹ | DeepSeek (кит.) | OpenRouter | 0.14 / 0.28 |
| Судья (eval) | `openai/gpt-5.4` (полная, не mini!) | OpenAI | OpenRouter | 2.50 / 15 |
| KG + testset | `google/gemini-3.1-flash-lite` | Google | OpenRouter | 0.25 / 1.50 |
| Эмбеддинги | `bge-m3` | — | локально (Ollama) | — |
| OCR | Tesseract | — | локально | — |

> ¹ Генератор `deepseek/deepseek-v4-flash` — **выбор B4 (2026-07-19)**: на golden-testset
> (11 в., судья gpt-5.4) обошёл прежний `qwen/qwen3.6-plus` по faithfulness (0.979 vs 0.947)
> и answer_relevancy (0.860 vs 0.763), вдвое быстрее (14с vs 28.6с) и дешевле ($0.14/$0.28 vs
> $0.33/$1.95 за 1M). Опасение про слабый русский НЕ подтвердилось — юр-терминология чистая
> (проверено глазами; отчёт-сравнение ответов: [b4-answers](https://claude.ai/code/artifact/f9a534ff-07fa-46e7-b482-ec8066c49776)).
> Fallback — `google/gemini-3.5-flash` (близко по качеству, но дороже и многословнее; `gemini-3.1-flash`
> на OpenRouter НЕ существует). ⚠ n=11 → для пуленепробиваемости расширить testset до 30+.
> Дизайн/план B4: [spec](docs/superpowers/specs/2026-07-19-b4-generator-selection-design.md).
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
- [x] **B4 — Этап 1 ✅ 2026-07-19** 🎯 Доказать выбор прод-генератора на данных: гоняли `qwen/qwen3.6-plus`
      (прежний выбор) против кандидатов — `deepseek/deepseek-v4-flash` (дешевле),
      `google/gemini-3.1-flash` (fallback), локальная модель через vLLM/Ollama —
      на ОДНОМ testset через Ragas+MLflow, судья `openai/gpt-5.4`. Убедиться что
      выбор лучший по цена/качество (в т.ч. русский на юр-терминологии ФПСР). Плюс
      поиграться с параметрами: `top_k`/`temperature`/`prompt` (query-time), `chunk_size`
      (index-time → переиндексация) → зафиксировать прод-конфиг с доказательством в MLflow.
      **Курированный golden-testset готов:** `backend/tests/eval/testset_golden.json`
      (11 вопросов, все 3 документа) → `make eval-golden` (~$0.7/прогон судьи). Факт-cost — в Langfuse (A3).
      **✅ Этап 1 (2026-07-19):** прогнали 3 генератора → **прод-генератор сменён qwen→`deepseek/deepseek-v4-flash`**
      (лучше по faithfulness+answer_relevancy, 2× быстрее, дешевле; русский чист — проверено глазами).
      `make b4-stage1`, эксперимент MLflow `b4-generator-selection`, отчёт-сравнение ответов:
      [b4-answers](https://claude.ai/code/artifact/f9a534ff-07fa-46e7-b482-ec8066c49776).
      Осталось (опц.): Этап 2 (`top_k`-свип на deepseek), Этап 3 (`chunk_size`).
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
1. **E4 (Security Gateway) ✅** — старт. Спека готова → writing-plans/TDD.
2. **Минимальный бот E1 — рано** (де-риск: демо-костяк обязан работать, хоть на текущем генераторе).
3. **B4** — прогон + сравнение в MLflow/Langfuse как демонстрация методологии тестирования.
4. **M1 (OpenRouter в live) ✅ + M2 (`run_in_threadpool`) ✅** — качество + конкурентность (= линия E3 ✅).
5. **Живые крутилки** `top_k`/`threshold`/`temperature`/`prompt` в админке — демо-фича/эксплорейшн, если останется время.

Минимальный набор под демо (must-have): **M1 (OpenRouter-генератор в live) + M2 (threadpool) + M3 (=E1 бот) + M4 (=rate-limit, половина E4 ✅)**. Injection-guard (вторая половина E4), vLLM, B4 — сверх минимума.

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
- [x] **E3** стабильность под параллельными юзерами → решается **M1 (OpenRouter в live) ✅
      + M2 (`run_in_threadpool`) ✅** из плана демо выше (узкое место — инференс, не HTTP)
- [x] **E4** 🔒 Security Gateway перед `RAGEngine.query` — первый user-facing контур
      закрываем защитным слоем из статьи об архитектуре AI-агентов. Дизайн утверждён,
      реализация позже: [security-gateway-design](docs/superpowers/specs/2026-07-14-security-gateway-design.md)
  - [x] rate-limit 10 запросов/день на `user_id` (Redis) — защита бюджета/DoS ⭐ **минимум для демо (=M4)**
  - [x] prompt-injection guard: правила (fast-path) + дешёвый LLM на спорных — витрина, опц. для демо
  - [x] видимость: лог решений + `/api/v1/gateway/stats` (сколько атак отбито)
  - [ ] (прод-потом) allowlist / PII-маскирование / кэш / авто-фолбэк модели
- [ ] **E5** 💰 Кэш ответов (экономия токенов) — Redis `cache:{question_hash} → answer+sources+confidence`,
      TTL ~1h (заложено ещё в исходном дизайне [design](docs/plans/2026-02-25-faq-rag-bot-design.md), не реализовано).
      Ещё один дешёвый локальный слой перед `RAGEngine.query` (там же, где E4-gateway):
      `rate-limit → injection → cache-lookup → (miss) query → cache-store`. Ключ — нормализованный
      вопрос (trim/lower/схлопнуть пробелы), кэш **глобальный** (ответ от документов, не от юзера).
      Нюансы: инвалидация при `add_document`/`delete_document` (или короткий TTL); кэшировать и
      «не нашёл» (тоже был LLM-вызов). Langfuse (A3): cache-hit = нет трейса генератора → видно экономию.
      Делать **после** рабочего бота (E1) — иначе кэшировать нечего. Небольшая задача (класс `AnswerCache` + вызов в `chat.py`).

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
| 16.07 | **E4 (Security Gateway) ✅** — пакет `app/core/gateway/`: rate-limit 10/день на user_id (Redis INCR/EXPIRE, fail-open), injection-guard (правила RU+EN + опц. LLM-стадия `google/gemini-3.1-flash-lite` по флагу), подключён как FastAPI-dependency на `/api/v1/chat` (429/400 до RAG), эндпоинт `/api/v1/gateway/stats`. Мастер-флаг `GATEWAY_ENABLED` + **admin-gated `X-Gateway-Bypass`**: веб-админка (наш лайв-тест) обходит gateway, бот-контур — нет (фронт шлёт заголовок в `endpoints.ts`). TDD: unit (rate-limit/rules/classifier/core/applies) + integration. | [security-gateway-design](docs/superpowers/specs/2026-07-14-security-gateway-design.md), [план](docs/superpowers/plans/2026-07-16-security-gateway-e4.md) |
| 16.07 | **M1+M2 ✅** — live-генератор переведён на OpenRouter `qwen/qwen3.6-plus` (эмбеддинги остались Ollama `bge-m3`): `OpenRouterAdapter` + `CompositeAdapter` (развязка генератор⊥эмбеддинги), фабрика собирает composite; `LLM_PROVIDER=openrouter` в compose (откат в 1 строку). `rag.query` в `run_in_threadpool` (не блокирует event loop). TDD: unit (адаптеры/фабрика) + integration. **⚠️ Важно:** `OPENROUTER_API_KEY` должен быть предоставлен в docker-compose (сейчас находится в `.env.eval`, а не `.env`) перед тем, как live-генерация заработает в демо. | [design](docs/superpowers/specs/2026-07-16-m1-m2-openrouter-live-design.md), [план](docs/superpowers/plans/2026-07-16-m1-m2-openrouter-live.md) |
| 19.07 | **B4 Этап 1 ✅** — доказательный выбор прод-генератора (SDD/TDD: спека→план→3 таска+ревью). Прогнали qwen/deepseek/gemini на golden-testset (11 в., судья gpt-5.4) через Ragas+MLflow (эксперимент `b4-generator-selection`) + cost в Langfuse. **Смена прод-генератора `qwen/qwen3.6-plus`→`deepseek/deepseek-v4-flash`**: лучше по faithfulness (0.979 vs 0.947) и answer_relevancy (0.860 vs 0.763), 2× быстрее (14с vs 28.6с), дешевле; русский на юр-терминологии подтверждён глазами (опасение снято). Правки live-пути: `config.py` + `docker-compose.yml` (+ `models.env` eval-дефолт). Попутно: `scripts/eval_config.py` + фикс бага кэша (ключ += генератор+top_k), env-driven `top_k`/`temperature`/experiment, MLflow-теги воспроизводимости, `mean_latency_s`, target `make b4-stage1`. Отлов: слаг `google/gemini-3.1-flash` не существует → fallback `gemini-3.5-flash`. Отчёт-сравнение ответов: [b4-answers (artifact)](https://claude.ai/code/artifact/f9a534ff-07fa-46e7-b482-ec8066c49776). | [spec](docs/superpowers/specs/2026-07-19-b4-generator-selection-design.md), [план](docs/superpowers/plans/2026-07-19-b4-generator-selection.md) |

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
