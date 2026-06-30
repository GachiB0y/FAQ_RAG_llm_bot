# Ragas + MLflow Evaluation — Project Status

**Дата создания:** 2026-06-28
**Цель:** Изучить Ragas + MLflow на реальном RAG-примере этого проекта, понять как работать и что это даёт.

---

## Что это и зачем

- **Ragas** (Apache 2.0, бесплатно) — Python-библиотека для оценки RAG. Считает faithfulness (опора на контекст, без галлюцинаций), answer_relevancy, context_precision/recall и др. Под капотом — LLM-as-judge.
- **MLflow** (Apache 2.0, бесплатно, self-hosted) — трекинг экспериментов и трассировка LLM-пайплайнов. Логирует параметры (chunk_size, top_k, модель) и метрики, сравнивает прогоны в UI. Имеет нативную интеграцию с LlamaIndex (`mlflow.llama_index.autolog()`) и Ragas (`mlflow.evaluate`).

---

## План: четыре шага

Шаги идут по росту сложности и зависимости друг от друга. Текущая работа — шаг 1.

### Шаг 1 — учебный изолированный пример (текущий)

**Цель:** пощупать оба инструмента на 50–100 строках кода. Production-код не трогаем.

**Что делаем:**
- Новый скрипт `backend/scripts/eval_rag.py`.
- Golden-датасет на ~10–15 пар (вопрос / эталонный ответ / релевантные чанки) на основе уже загруженных документов.
- Прогон через **существующий** `RAGEngine` из `backend/app/core/rag/engine.py`.
- Расчёт ragas-метрик: `faithfulness`, `answer_relevancy`, `context_precision`, `context_recall`.
- Логирование в локальный MLflow (SQLite backend store + папка `mlruns/` для артефактов).
- UI: `mlflow ui --backend-store-uri sqlite:///mlflow.db` → http://localhost:5000.
- Добавить зависимости в `backend/pyproject.toml`: `ragas`, `mlflow`, `datasets`.

**Что НЕ трогаем:**
- docker-compose
- основной RAG-пайплайн
- тесты, CI
- модели в Ollama (кроме pull нового судьи)

### Шаг 2 — интеграция MLflow в проект (отложено)

Откладывается до завершения шага 1. Войдёт:
- сервис `mlflow` в `docker-compose.yml` (Postgres backend, MinIO для артефактов — уже есть рядом в окружении)
- автотрассировка в основном RAG-пайплайне (`mlflow.llama_index.autolog()`)
- golden-датасет переезжает в `backend/tests/eval/`
- Makefile-таргет `make eval` для прогона
- (опционально) CI-job, который падает если faithfulness упал ниже порога

### Шаг 3 — Hybrid search в retrieval (отложено)

Сейчас retrieval работает только на dense (vector) поиске через bge-m3.
Для устава со статьями («ст. 14.6», «п. 152») dense проваливается — нужен
sparse-компонент (BM25 / keyword).

Что войдёт:
- `QdrantVectorStore(enable_hybrid=True)` — Qdrant с 1.10 умеет hybrid в одной коллекции
- Sparse-вектора генерируются той же `bge-m3` (она умеет dense + sparse одновременно)
- Reciprocal Rank Fusion для слияния результатов
- Перевычислить эмбеддинги существующих чанков (или удалить коллекцию и переиндексировать)
- Прогнать тот же ragas eval — сравнить с шагом 1 (ожидаем рост context_recall на специфичных вопросах со статьями)

Зачем именно после MLflow: чтобы сравнение «было/стало» осело в MLflow как два прогона.

### Шаг 4 — Prefect для оркестрации пайплайнов (отложено)

Когда документов станет много (полный корпус компании с Яндекс-Диска — см. ниже),
синхронный POST `/documents` перестанет годиться. Нужен оркестратор.

Что войдёт:
- Сервис `prefect-server` в docker-compose
- Flow `ingest_corpus`: load → parse → chunk → embed → upsert в Qdrant. Каждая стадия — отдельная task с ретраями.
- Flow `nightly_eval`: ragas-прогон на golden-датасете → MLflow → алёрт если faithfulness < порога
- (опц.) Flow `reindex`: при смене embedding-модели полностью перебилдить коллекцию

Альтернативы которые тоже рассматривались:
- **Celery + Redis** — проще, у вас уже Redis есть, но без UI и метрик задач
- **Airflow** — тяжелее, более «классический» оркестратор, overkill для пары пайплайнов
- Просто `cron` + python — для совсем маленьких задач, не масштабируется

---

## Решения по моделям

| Роль | Модель | Почему |
|---|---|---|
| **Генератор** (отвечает на вопросы — оцениваемый) | `qwen3:1.7b` (Ollama) | То, что уже стоит в проекте — её и оцениваем |
| **Эмбеддинги** (для retrieval и для метрик Answer Similarity) | `bge-m3` (Ollama) | Уже стоит, 1024-dim, мультиязычная |
| **Судья** (LLM-as-judge в Ragas) | `qwen2.5:7b` (Ollama) | Бесплатно, без API-ключей. Минус — медленнее, оценки шумнее чем у Haiku/GPT-4o. Для учебного примера ок |

**Альтернативы судьи** (на случай если qwen2.5:7b даст слишком шумные оценки):
- Claude Haiku 4.5 через API (`ANTHROPIC_API_KEY`) — ~30–60с/прогон, ~$0.05
- GPT-4o-mini через API (`OPENAI_API_KEY`) — ~30–60с/прогон, ~$0.05

---

## Состояние данных (на 2026-06-28)

Подняты `qdrant` + `postgres` контейнеры из docker-compose. Volumes сохранились с марта.

**Документы в Qdrant (collection `documents`)** (старый набор удалён, актуальный — из `docs_for_test_rag/`):

| Файл | Стр. | Чанков | Содержимое |
|---|---|---|---|
| Положение о членстве ОСОО ФПСР.pdf | 12 | 31 | Условия приёма, права/обязанности, БЕКОСО, исключение |
| Правила вида спорта практическая стрельба с 04.12.2025.pdf | 145 | 385 | Правила от Минспорта РФ, дисциплины по МКПС |
| кратко-о-процессе-вступления.pdf | 1 | 2 | **PDF-инфографика — текст не извлекается** (custom-шрифт). Для eval бесполезен; пример проблемы, лечится OCR |

**Итого:** 418 чанков, вектора 1024-dim (bge-m3), cosine distance.

> Golden-dataset переписан под "Положение о членстве" — 10 вопросов, для
> большинства из них правильный ответ находится в одной-двух статьях, что
> хорошо для отладки context_precision/context_recall.

### Реальный корпус компании (для шагов 3–4)

Источник: https://disk.yandex.ru/d/B9Egtwwvoxbnbw (Яндекс-Диск, доступ у пользователя).

Что нужно сделать перед шагом 3 (когда дойдём):
1. Скачать архив с Яндекс-Диска в `backend/uploads/corpus/` (или другую папку — главное volume-mounted)
2. Прогнать через `RAGEngine.add_document(...)` — либо UI, либо batch-скрипт
3. Решить: оставлять текущие 2 документа в коллекции или начать с чистого листа (`/documents` DELETE → reindex)
4. Расширить golden-датасет реальными FAQ компании (если есть)

> Скачивание из Яндекс-Диска требует либо публичной ссылки через `wget`/`curl` с
> правильным API-эндпоинтом, либо ручной скачки в браузере. Сделаем когда дойдём
> до шага 3.

---

## Текущий план эксперимента — итерация RAG через MLflow

Цель: сравнить **dense-only retrieval** с **hybrid (dense + BM25)** на одном и том же
сгенерированном датасете, чтобы понять реально ли hybrid помогает на корпусе ФПСР.

```
┌────────────────────────────────────────────────────────────────┐
│ Прогон #1 (BASELINE) — что мы сейчас запустили                │
│                                                                 │
│  Retrieval: Qdrant dense (bge-m3, top_k=5, cosine)             │
│  Generator: qwen3:1.7b (Ollama)                                 │
│  Dataset:   testset_auto.json (20 авто-вопросов, 3 persona)    │
│  Judge:     google/gemma-4-31b-it:free (OpenRouter)            │
│                                                                 │
│  → MLflow run "json-qwen3:1.7b-judge-gemma-4-31b-it-k5"        │
└────────────────────────────────────────────────────────────────┘
                              ↓
                  (включаем hybrid в QdrantVectorStore,
                   переиндексируем коллекцию)
                              ↓
┌────────────────────────────────────────────────────────────────┐
│ Прогон #2 (HYBRID) — следующая итерация                       │
│                                                                 │
│  Retrieval: Qdrant dense + sparse (bge-m3 multi-functional),   │
│             RRF fusion, top_k=5                                 │
│  Всё остальное — то же самое                                    │
│                                                                 │
│  → MLflow run "json-qwen3:1.7b-judge-gemma-4-31b-it-k5-hybrid" │
└────────────────────────────────────────────────────────────────┘
                              ↓
                  MLflow UI → Compare runs:
                  смотрим дельту по каждой метрике
```

### Что смотреть в MLflow UI

| Метрика | Что показывает | Ожидание после hybrid |
|---|---|---|
| `mean_context_recall` | Нашёл ли retriever ВСЁ нужное | ↑ — главный эффект hybrid |
| `mean_context_precision` | Не приволок ли лишнего | возможно ↓ незначительно |
| `mean_faithfulness` | Не галлюцинирует ли LLM | ≈ (зависит от качества retrieval) |
| `mean_answer_relevancy` | Релевантен ли ответ | ≈ или ↑ |

Плюс **срезы по типу вопроса** (мы их логируем):
- `by_synth__single_hop_specifc__mean_context_recall`
- `by_synth__multi_hop_abstract__mean_context_recall`
- `by_synth__multi_hop_specific__mean_context_recall`

Hybrid обычно бустит multi-hop сильнее, потому что один из двух нужных чанков
часто содержит конкретный термин или цифру, который dense пропускает.

### Доступ к MLflow UI

`mlflow.db` лежит на хосте через volume mount (`./backend/mlflow.db`). Поэтому UI
запускается **в отдельном sidecar-контейнере**, не трогая основной backend.

```bash
# одноразовый запуск UI:
docker run --rm -d --name mlflow-ui -p 5050:5050 \
    -v $(pwd)/backend:/data python:3.11-slim \
    sh -c "pip install --quiet mlflow && \
           mlflow ui --backend-store-uri sqlite:////data/mlflow.db \
                     --host 0.0.0.0 --port 5050"

# открыть: http://localhost:5050

# остановить:
docker stop mlflow-ui
```

> Порт 5000 на macOS обычно занят AirPlay Receiver, поэтому 5050.

## Прогресс

- [x] Проанализирован проект
- [x] Решён вопрос про Claude (нужен API-ключ от console.anthropic.com — отказались, идём через Ollama)
- [x] Выбраны модели (генератор/эмбеддинги/судья)
- [x] Проверено состояние Qdrant и Postgres — данные на месте, оба документа доступны
- [x] Создан этот файл со статусом
- [x] Подтянут `qwen2.5:7b` в Ollama (4.7 GB)
- [x] Установлены `ragas==0.2.15`, `mlflow==3.14.0`, `langchain-ollama==0.2.3` в backend контейнере
- [x] Написан `backend/scripts/eval_rag.py` — 8 вопросов golden-датасета на основе PDF (устав) и TXT (FAQ)
- [ ] Прогон eval (запущен в фоне, ~15–25 минут)
- [ ] Посмотреть результат в MLflow UI
- [ ] Решить про шаг 2

## Как запускать

**Eval-прогон** (внутри уже работающего backend-контейнера):
```bash
docker exec faq_rag_llm_bot-backend-1 python scripts/eval_rag.py
```

**MLflow UI** (отдельный процесс):
```bash
# поднимаем UI на 5000 порту, mlflow.db уже создан скриптом
docker exec -d faq_rag_llm_bot-backend-1 \
    mlflow ui --backend-store-uri sqlite:////app/mlflow.db \
              --host 0.0.0.0 --port 5000
# затем пробросить порт (если docker compose port 5000 ещё не открыт):
docker exec faq_rag_llm_bot-backend-1 lsof -i:5000  # проверка
# Открыть http://localhost:5000 в браузере
```

> Замечание: порт 5000 не проброшен наружу в docker-compose.yml — для UI либо
> делаем `docker compose run -p 5000:5000 backend mlflow ui ...`, либо запускаем
> mlflow ui на хосте против `backend/mlflow.db` (volume mount уже есть).

## Зависимости (несовместимости)

`ragas 0.4.x` импортит `langchain_community.chat_models.vertexai`, которого нет
в свежем `langchain-community>=0.4`. Зафиксировали совместимую связку:

```
ragas==0.2.15
langchain<0.4
langchain-community<0.4
langchain-core<0.4
langchain-ollama<0.3
datasets<3
```

Из backend контейнера убраны `langchain-classic` и `langgraph-*` — конфликтовали
с langchain-core 0.3 (которого требует ragas 0.2.x). На основной flow это
не влияет (langgraph не используется в проекте).

---

## Ссылки

- Ragas: https://github.com/explodinggradients/ragas
- MLflow LLM evaluate: https://mlflow.org/docs/latest/llms/llm-evaluate/index.html
- MLflow ↔ LlamaIndex: https://mlflow.org/docs/latest/llms/llama-index/index.html
- Qdrant Hybrid Search: https://qdrant.tech/articles/hybrid-search/
- Prefect: https://docs.prefect.io/
- BGE-m3 (multi-functional embedding): https://huggingface.co/BAAI/bge-m3
- Корпус компании (Яндекс-Диск): https://disk.yandex.ru/d/B9Egtwwvoxbnbw
