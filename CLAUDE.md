# CLAUDE.md — контекст проекта для AI-ассистента

Этот файл читается AI-ассистентом (Claude Code) в начале работы. Здесь — карта
проекта и ссылки на ключевые документы.

## Что за проект

**FAQ RAG Bot** — чат-бот для ответов на вопросы по документам компании (ФПСР).
Стек: FastAPI + LlamaIndex + Qdrant + Ollama + Postgres + Redis, фронт React (FSD).
Плюс исследовательская линия: оценка RAG через Ragas + MLflow, MLOps-практики.

## 📌 Главные документы (читать в этом порядке)

1. **[PROJECT_STATUS.md](PROJECT_STATUS.md)** — 📊 единая точка правды: текущий
   фокус, открытые задачи, хронология разработки. **Открывать первым каждую сессию.**
2. **[RAG_AGENT_WORKFLOW.md](RAG_AGENT_WORKFLOW.md)** — 🔄 как у нас выстроен флоу
   разработки RAG-агентов (8 фаз, какой инструмент на каком шаге и зачем).
   Обращаться когда нужно понять «где мы» и «что дальше по-хорошему».
3. **[README.md](README.md)** — обзор проекта, quick start, как запустить.

## Детальные документы (`docs/plans/`)

- `2026-07-06-mlops-implementation-status.md` — трекер MLOps-внедрения (uv→Makefile→Langfuse→DVC→CI)
- `2026-07-06-mlops-maturity-analysis.md` — анализ «7 болей ML» на нашем проекте
- `2026-07-02-production-tooling-roadmap.md` — vLLM / LangGraph / pgvector / Langfuse
- `2026-06-30-clean-experiment-report.md` — финальный отчёт эксперимента dense vs hybrid
- `2026-06-28-ragas-full-workflow.md` — теория Ragas (KG, personas, метрики)

## Как мы работаем

- **Философия:** Evaluation-Driven Development — сначала система оценки, потом
  оптимизация. Подробнее — в RAG_AGENT_WORKFLOW.md.
- **Ведение статуса:** в конце сессии обновляем PROJECT_STATUS.md (галочки +
  строка в хронологию).
- **Git:** ветка `dev` для текущей работы, `main` — стабильная. Коммитим/пушим
  только по явной просьбе.
- **Секреты:** `.env.eval` (ключ OpenRouter) — локальный, в git не попадает (gitignore).

## Технические заметки

- LLM локально через **Ollama** (bge-m3 embeddings, qwen3:1.7b) — для dev.
- Внешние LLM через **OpenRouter** (ключ в `.env.eval`) — для eval/экспериментов.
- Eval-зависимости (ragas==0.2.15, langchain<0.4 и пины) ставились вручную в
  контейнер — **это боль #5, лечится через uv (задача A1)**.
- Скрипты эксперимента — в `backend/scripts/` (`eval_rag.py`, `generate_kg.py`,
  `generate_testset.py`, `ingest_*.py`, `ocr_image_pdf.py`, `_hybrid_retriever.py`).
