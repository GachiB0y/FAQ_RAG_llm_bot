# FAQ RAG Bot

RAG-бот для ответов на вопросы по корпоративной документации с автоматической оценкой качества через **Ragas + MLflow**. Тестовый корпус — документы Федерации Практической Стрельбы России (ФПСР).

> Pet-проект, в котором собран полноценный pipeline: от парсинга PDF до сравнительной оценки разных стратегий retrieval в MLflow UI.

---

## Что внутри

- **Production-ready RAG-стек:** FastAPI + LlamaIndex + Qdrant + Ollama + Postgres + Redis
- **React-фронт** (FSD-архитектура, Chakra UI, TanStack Query, react-intl)
- **Авто-оценка RAG** через Ragas: knowledge graph → testset с personas → 4 метрики качества
- **MLflow** для трекинга экспериментов и сравнения прогонов
- **Hybrid search experiment**: dense (bge-m3) vs hybrid (dense + BM25 + RRF) — с измеримыми результатами
- **OCR** через Tesseract для PDF-картинок

---

## Архитектура

```
┌────────────────────────────────────────────────────────────────┐
│                       FRONTEND (React 19)                       │
│             FSD · Chakra UI · TanStack · i18n                   │
└──────────────────────────────┬─────────────────────────────────┘
                               │ HTTPS · JWT
                               ▼
┌────────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI + LlamaIndex)              │
│  - Auth (JWT)    - Chat history   - Document mgmt              │
│  - RAGEngine: retriever → LLM-генерация ответа                 │
└─────┬──────────────┬──────────────┬──────────────┬─────────────┘
      │              │              │              │
      ▼              ▼              ▼              ▼
┌─────────┐  ┌─────────────┐  ┌─────────┐  ┌──────────────┐
│Postgres │  │   Qdrant    │  │  Redis  │  │   Ollama     │
│ (users, │  │ (vectors:   │  │ (chat   │  │ (bge-m3 +    │
│ chats,  │  │  dense +    │  │  cache) │  │  qwen3:1.7b) │
│  docs)  │  │  sparse)    │  │         │  │              │
└─────────┘  └─────────────┘  └─────────┘  └──────────────┘
```

---

## Quick start

### 1. Запуск всего стека

```bash
# поднять postgres + redis + qdrant + ollama + backend + frontend
docker compose up -d

# первый запуск: backend сам подтянет qwen3:1.7b и bge-m3 в Ollama (~3 GB)
```

После старта:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/docs
- Qdrant UI: http://localhost:6333/dashboard

### 2. Дефолтный админ

```
admin@example.com / admin123
```

Создаётся автоматически при первом старте backend.

### 3. Загрузка документов

UI → Documents → Upload. Или через API:
```bash
curl -X POST http://localhost:8000/api/v1/documents \
  -H "Authorization: Bearer <token>" \
  -F "file=@your_doc.pdf"
```

Поддерживаются: **PDF, DOCX, TXT, MD, HTML, XLSX**.

### 4. Чат

UI → Chat. История сохраняется, infinite scroll включён. Ответы цитируют источники.

---

## Эксперимент: Dense vs Hybrid retrieval

Главная фишка репо — **полная связка Ragas + MLflow для оценки RAG**. Сравнили два варианта retrieval на одинаковом тестовом наборе.

### Результаты (на корпусе ФПСР)

| Метрика | Dense (bge-m3) | Hybrid (dense + BM25 + RRF) | Δ |
|---|---|---|---|
| Faithfulness | 0.826 | **1.000** | **+21%** |
| Answer Relevancy | 0.700 | **0.816** | **+17%** |
| Context Precision | 0.606 | **0.917** | **+51%** |
| Context Recall | 0.736 | **1.000** | **+36%** |

**Вывод:** на корпусе с формальными ссылками (статьи, ФЗ, аббревиатуры) hybrid search кардинально лучше — embedding-модели плохо различают близкие термины (ФЗ № 115 ≈ ФЗ № 150 по cosine), BM25 их разводит точно.

### Воспроизвести эксперимент

```bash
# 0. Скачать корпус (см. docs/plans/2026-06-29-clean-experiment-plan.md)

# 1. Загрузить корпус в Qdrant (2 коллекции — dense и hybrid)
docker exec faq_rag_llm_bot-backend-1 python scripts/ingest_local.py /tmp/corpus
docker exec faq_rag_llm_bot-backend-1 python scripts/ingest_hybrid.py

# 2. Построить knowledge graph (нужен OPENROUTER_API_KEY в .env.eval)
docker exec -e OPENROUTER_API_KEY=$KEY faq_rag_llm_bot-backend-1 \
  python scripts/generate_kg.py

# 3. Сгенерить testset с personas
docker exec -e OPENROUTER_API_KEY=$KEY faq_rag_llm_bot-backend-1 \
  python scripts/generate_testset.py

# 4. Прогон eval (DENSE)
docker exec -e OPENROUTER_API_KEY=$KEY -e DATASET_SOURCE=json \
  faq_rag_llm_bot-backend-1 python scripts/eval_rag.py

# 5. Прогон eval (HYBRID — тот же датасет, другой retrieval)
docker exec -e OPENROUTER_API_KEY=$KEY -e DATASET_SOURCE=json -e HYBRID=true \
  faq_rag_llm_bot-backend-1 python scripts/eval_rag.py

# 6. Смотрим результаты в MLflow UI
docker run --rm -d --name mlflow-ui -p 5050:5050 \
  -v $(pwd)/backend:/app python:3.11-slim \
  sh -c "pip install --quiet mlflow && \
         mlflow ui --backend-store-uri sqlite:////app/mlflow.db --host 0.0.0.0 --port 5050"
# открыть http://localhost:5050
```

---

## Структура

```
.
├── backend/
│   ├── app/
│   │   ├── api/v1/         # FastAPI endpoints (auth, chat, documents, users, settings)
│   │   ├── core/
│   │   │   ├── llm/        # LLM-адаптеры (Ollama, OpenAI, factory)
│   │   │   └── rag/        # Retriever, Engine, Loader, Chunker
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   └── services/       # Бизнес-логика
│   ├── scripts/
│   │   ├── ingest_local.py        # Load PDFs → dense Qdrant
│   │   ├── ingest_hybrid.py       # Load PDFs → hybrid Qdrant (dense + sparse)
│   │   ├── generate_kg.py         # Build Ragas knowledge graph
│   │   ├── generate_testset.py    # Generate testset with personas
│   │   ├── eval_rag.py            # Run RAG + Ragas evaluate → MLflow
│   │   ├── ocr_image_pdf.py       # Tesseract OCR for image PDFs
│   │   └── _hybrid_retriever.py   # HybridQdrantRetriever (dense + BM25 + RRF)
│   ├── tests/
│   │   └── eval/
│   │       └── kg.json     # Сохранённый knowledge graph эксперимента
│   ├── alembic/            # DB migrations
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/                # FSD: shared → entities → features → widgets → pages
│   ├── Dockerfile
│   └── package.json
├── docs/
│   └── plans/              # Все design-docs, отчёты, гайды по эксперименту
├── tests/
│   └── e2e/                # E2E test cases (YAML)
└── docker-compose.yml
```

---

## Документация по эксперименту

В `docs/plans/`:

| Документ | Что внутри |
|---|---|
| `2026-06-28-ragas-mlflow-eval-status.md` | Статус-файл с roadmap (4 шага: учебный пример → интеграция → hybrid → Prefect) |
| `2026-06-28-ragas-full-workflow.md` | Теоретический гайд по Ragas: KG, personas, синтезаторы, метрики |
| `2026-06-29-ragas-experiment-report.md` | **Полный отчёт об эксперименте** dense vs hybrid с методологией и анализом |
| `2026-06-29-ragas-experiment-slides.md` | Презентация в формате Marp |
| `2026-06-29-ragas-experiment-slides.html` | Та же презентация в HTML (Reveal.js) |
| `2026-06-29-clean-experiment-plan.md` | План «чистого» повторного эксперимента с исправлениями методологических проблем |

---

## Tech stack

### Backend
- **Python 3.11** · FastAPI · uvicorn · SQLAlchemy + asyncpg · Alembic
- **LlamaIndex** (RAG-фреймворк) · **Qdrant** (vector DB) · **Ragas** (eval)
- **MLflow** (трекинг экспериментов)
- **FastEmbed** (BM25 sparse vectors)
- **PyMuPDF** + **Tesseract** (OCR)
- **JWT** + bcrypt

### Frontend
- **React 19** · **TypeScript** · **Vite**
- **Chakra UI v2** · **TanStack Query v5** · **Zustand**
- **react-intl** (RU/EN) · **react-router v7**
- **FSD** (Feature-Sliced Design)

### LLM-провайдеры
- **Ollama** (локально): bge-m3 embeddings, qwen3:1.7b
- **OpenRouter** (внешние free/paid): gemma-4-31b, nemotron-3-super-120b, и т.д.
- Адаптеры в `backend/app/core/llm/` — легко добавить нового провайдера

---

## Лицензия

MIT (можно делать что угодно, упомяните автора). Тестовые документы ФПСР — публичные источники.

---

**Repo:** https://github.com/GachiB0y/FAQ_RAG_llm_bot
**Author:** [Alexander Volkov](https://github.com/GachiB0y)
