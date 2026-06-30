---
marp: true
theme: default
paginate: true
header: 'Ragas + MLflow для оценки RAG'
footer: 'FAQ RAG Bot · ФПСР · июнь 2026'
style: |
  section { font-size: 24px; }
  h1 { color: #1f4e79; }
  h2 { color: #2e75b6; border-bottom: 2px solid #2e75b6; padding-bottom: 6px; }
  table { font-size: 18px; }
  .big-num { font-size: 56px; font-weight: bold; color: #1f4e79; }
  .delta-up { color: #2e7d32; font-weight: bold; }
  .delta-down { color: #c62828; font-weight: bold; }
  code { background: #f5f5f5; padding: 2px 5px; border-radius: 3px; }
---

<!-- _class: lead -->

# Оценка RAG-системы через **Ragas + MLflow**

### Эксперимент на корпусе документов ФПСР

**Гипотеза:** hybrid retrieval (dense + BM25) должен превзойти dense-only на корпусе с формальными ссылками (статьи, ФЗ, аббревиатуры).

Александр Волков · июнь 2026

---

## Зачем оценивать RAG автоматически?

- **Любое изменение** в RAG-pipeline (модель, чанкер, retriever, prompt) — может улучшить **или ухудшить** качество
- **Ручная проверка не масштабируется**: 5 примеров — не показатель, 100 — никто читать не будет
- Нужен **воспроизводимый, числовой** способ:
  - сравнить «было vs стало»
  - блокировать регрессии в CI
  - объяснить команде/руководству «почему это лучше»

---

## Цель и гипотеза

### Цель
1. Освоить **Ragas + MLflow** на реальном проекте
2. Измерить качество текущего RAG
3. **Проверить:** даёт ли hybrid search прирост на нашем корпусе

### Гипотеза
На корпусе с **формальными ссылками** (ФЗ № 7-ФЗ, § 21.3, БЕКОСО, МКПС) dense-vector search проигрывает sparse-поиску по recall — потому что:

- Embedding-модель «понимает темы», но плохо различает близкие термины
- BM25 ищет по **лексическому совпадению** → находит точные ссылки моментально
- **RRF-фьюжен** даёт лучшее из двух миров

---

## Архитектура pipeline

```
PDF → chunks → Knowledge Graph → Test set (с personas) → RAG → Ragas judge → MLflow
       (512т)    (Ragas)         (20 вопросов)         (top_k=5) (4 метрики)  (compare)
```

**Что независимо от retrieval-режима:**
- Парсер PDF, chunker (chunk_size=512, overlap=50)
- Knowledge Graph + Test set (один раз, переиспользуется)
- LLM-генератор и LLM-судья (одни и те же в обоих прогонах)

**Что меняется:**
- Только **retrieval mode**: `dense` vs `hybrid`

---

## Стек и модели

| Слой | Инструмент |
|---|---|
| Векторная БД | Qdrant |
| RAG-фреймворк | LlamaIndex |
| Eval-фреймворк | Ragas 0.2.15 |
| Трекинг | MLflow 3.14 |
| Sparse-векторы | FastEmbed (BM25) |

| Роль | Модель | Где |
|---|---|---|
| Embeddings (dense) | `bge-m3` 1024-dim | Ollama локально |
| Sparse encoder | `Qdrant/bm25` | FastEmbed локально |
| RAG generator | `nemotron-3-super-120b:free` | OpenRouter |
| KG / testset / judge | `gemma-4-31b-it:free` | OpenRouter |

---

## Корпус

3 PDF Федерации Практической Стрельбы России:

| Файл | Стр. | Чанков |
|---|---|---|
| Положение о членстве ОСОО ФПСР | 12 | 31 |
| Правила вида спорта 2025 | 145 | 385 |
| Кратко о вступлении (картинка) | 1 | 2 |
| **Итого** | **158** | **418** |

**2 коллекции в Qdrant:**
- `documents` — только dense (1024-dim)
- `documents_hybrid` — dense + sparse (BM25)

---

## Тестовый набор: 20 вопросов с personas

Сгенерированы через **Ragas TestsetGenerator** из knowledge graph.

### 3 persona
- **novice** — «слыш ты там по ФЗ № 114 че там написано»
- **instructor** — терминологичный, со сроками
- **lawyer** — точные ссылки на ФЗ № 7, 82, 150, 329

### Distribution синтезаторов
| Тип | % | Шт |
|---|---|---|
| Single-hop (один чанк) | 60% | 12 |
| Multi-hop abstract (концепт) | 20% | 4 |
| Multi-hop specific (сравнение) | 20% | 4 |

---

## Метрики Ragas (LLM-as-judge)

### Про LLM-генератор
- **Faithfulness** — нет ли галлюцинаций? Доля claims в ответе, подкреплённых контекстом
- **Answer Relevancy** — отвечает ли на вопрос? Cosine между «восстановленным» вопросом и оригиналом

### Про retrieval
- **Context Precision (with ref)** — не приволок ли мусор? Доля релевантных чанков в top-k
- **Context Recall** — нашёл ли всё нужное? Доля claims из reference, выводимых из контекста

---

## Эксперимент

**Сценарий:** прогнать 20 вопросов через RAG **дважды** — единственное отличие `retrieval_mode`.

| Параметр | Dense run | Hybrid run |
|---|---|---|
| retrieval | bge-m3 (cosine, top_k=5) | bge-m3 **+ BM25** (RRF, top_k=5) |
| generator | nemotron-120b | nemotron-120b |
| judge | gemma-4-31b | gemma-4-31b |
| dataset | testset_auto.json | testset_auto.json |

→ Два MLflow run-а готовы к compare-сравнению.

---

## Результаты

| Метрика | Dense | Hybrid | Δ |
|---|---|---|---|
| Faithfulness | 0.826 | **1.000** | <span class="delta-up">+21%</span> |
| Answer Relevancy | 0.700 | **0.816** | <span class="delta-up">+17%</span> |
| Context Precision | 0.606 | **0.917** | <span class="delta-up">+51%</span> |
| Context Recall | 0.736 | **1.000** | <span class="delta-up">+36%</span> |

### **Hybrid выиграл по всем 4 метрикам.**

---

## Что произошло на каждой метрике

### Context Recall: 0.736 → **1.000** (+36%)
Dense пропускал ~25% нужной инфы — типично на вопросах со ссылками на статьи и ФЗ. BM25 находит точные совпадения, RRF поднимает их в топ-5.

### Context Precision: 0.606 → **0.917** (+51%) ← самый большой прирост
При dense-only **40% top-5 были мусором** → LLM отвлекалась. Hybrid отсёк нерелевантные.

### Faithfulness: 0.826 → **1.000** (+21%)
Когда контекст полный, LLM **не нужно** «достраивать» из общих знаний → нет галлюцинаций. Достигла идеала **1.0**.

### Answer Relevancy: 0.700 → **0.816** (+17%)
Точнее контекст → точнее ответ по сути. Особенно заметно на multi-hop.

---

## Главный график

```
       Dense  ████████░░  0.83
   Faithful  ██████████  1.00 (+21%)
                          
   Answer    ███████░░░  0.70
   Relevancy ████████░░  0.82 (+17%)
                          
   Context   ██████░░░░  0.61
   Precision █████████░  0.92 (+51%)
                          
   Context   ███████░░░  0.74
   Recall    ██████████  1.00 (+36%)
```

*(полные графики — в MLflow UI → Compare → Parallel Coordinates Plot)*

---

## Что это означает в практике

- **На корпусе с формализмами** (ФЗ, статьи, аббревиатуры) **hybrid обязателен**
- Embedding-модели «понимают темы», но **проваливаются** на точных терминах (ФЗ № 115 vs ФЗ № 150 — почти одинаковый embedding)
- BM25 эти случаи решает **из коробки**, добавление стоит ~20 строк кода
- Это **самое дешёвое улучшение** RAG в данном кейсе

### Что попадёт в прод
- `enable_hybrid=True` в `QdrantVectorStore`
- Переиндексация существующих 418 чанков с sparse-векторами
- BM25 как часть штатного pipeline

---

## Что мы узнали об инструментах

### Ragas
- Knowledge graph + Personas → **реалистичный** тестовый набор, не просто «придумай 10 вопросов»
- 4 метрики покрывают и **LLM-генератор**, и **retrieval** независимо
- LLM-as-judge — точно настолько умное, насколько модель-судья

### MLflow
- **Compare-режим** для двух run-ов — самый ценный
- Логирование `by_synth__*` срезов даёт детализацию по типу вопроса
- SQLite-backend + локальный артефакт-стор → подходит для self-hosted

---

## Ограничения эксперимента

### Методологические
- **20 вопросов** — статистика хлипкая. Стоит расширить до 50–100
- **gemma-4-31b** был и testset-генератором, и судьёй — потенциальный bias. Для прода нужен Claude Haiku / GPT-4 в роли судьи
- **Картинка-PDF** парсится в кракозябры — BM25 цепляет мусор. Нужен OCR

### Технические
- **OpenRouter free** имеет лимиты (20 RPM, 2000/день), регулярные 429-ки
- **Ollama на Mac** OOM-ит при попытке держать несколько моделей одновременно — настройка `num_ctx`

---

## Дальнейшие шаги

### Короткие (1–2 дня)
1. **Hybrid в прод**: `app/core/rag/retriever.py` → `enable_hybrid=True` + реиндексация
2. **Платный судья**: Claude Haiku 4.5 ($0.10 за полный прогон) → стабильные оценки
3. **OCR**: `pytesseract` для картинок-PDF

### Средние (1–2 недели)
4. **Расширение датасета** до 50–100 вопросов + ручная курация
5. **CI-интеграция**: GitHub Action, падает если faithfulness просел > 5%

### Длинные (1–2 месяца)
6. **Prefect** для оркестрации ingest и nightly eval
7. **Полный корпус ФПСР** (10 директорий с Яндекс-Диска)
8. **Реальные user-вопросы** вместо/в дополнение к auto-generated

---

## Артефакты эксперимента

### В репозитории
- `backend/scripts/eval_rag.py` — главный eval (dense/hybrid, openrouter/ollama)
- `backend/scripts/generate_kg.py` — knowledge graph
- `backend/scripts/generate_testset.py` — testset с personas
- `backend/scripts/_hybrid_retriever.py` — hybrid retriever (dense + BM25 + RRF)
- `backend/tests/eval/readable/compare_dense_vs_hybrid.xlsx` — сравнение

### MLflow
- UI: http://localhost:5050 → ragas-eval → Compare
- BD: `backend/mlflow.db` (SQLite)

### Документация
- `docs/plans/2026-06-29-ragas-experiment-report.md` — полный отчёт
- `docs/plans/2026-06-28-ragas-full-workflow.md` — теория Ragas

---

<!-- _class: lead -->

## Спасибо!

### Вопросы?

📂 Репозиторий: `FAQ_RAG_llm_bot/`
📊 MLflow: http://localhost:5050
📄 Полный отчёт: `docs/plans/2026-06-29-ragas-experiment-report.md`
