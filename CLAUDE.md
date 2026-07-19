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

---

# Поведенческие правила (behavioral guidelines)

> Источник: https://github.com/multica-ai/andrej-karpathy-skills/blob/main/CLAUDE.md
> Общие правила, снижающие типичные ошибки LLM при разработке. Применять вместе
> с проектными инструкциями выше.

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
