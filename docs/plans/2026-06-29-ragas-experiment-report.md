# Отчёт об эксперименте: оценка RAG-системы через Ragas + MLflow

**Дата эксперимента:** 28-29 июня 2026
**Проект:** FAQ RAG Bot (ФПСР — Федерация Практической Стрельбы России)
**Автор:** Александр Волков
**Длительность:** ~2 рабочих дня

---

## TL;DR

Развернули полный фреймворк автоматической оценки RAG-системы на базе **Ragas + MLflow**.
Прогнали два варианта retrieval — **dense (только bge-m3)** vs **hybrid (bge-m3 + BM25 + RRF)** — на одинаковом наборе из 20 авто-сгенерированных вопросов с тремя personas.

**Hybrid выиграл по всем 4 метрикам с большим запасом:**

| Метрика | Dense | Hybrid | Δ |
|---|---|---|---|
| Faithfulness | 0.826 | **1.000** | +21% |
| Answer Relevancy | 0.700 | **0.816** | +17% |
| Context Precision | 0.606 | **0.917** | +51% |
| Context Recall | 0.736 | **1.000** | +36% |

**Главный вывод:** для корпуса с формальными отсылками (статьи ФЗ, аббревиатуры, нумерация пунктов) **hybrid search — критически важная фича.** Dense-only пропускает специфичные термины, BM25 их находит.

---

## 1. Цель эксперимента

1. **Освоить Ragas + MLflow** на реальном проекте, понять как они работают.
2. **Измерить качество** текущего RAG-pipeline.
3. **Проверить гипотезу:** добавление hybrid search улучшит retrieval на корпусе с
   формализмами (ФЗ, статьи, аббревиатуры).
4. **Получить методологию** для дальнейших итераций — как любое изменение в RAG
   (новая модель, другой chunker, новый retriever) измерять одинаково и
   сравнивать в MLflow.

---

## 2. Гипотеза

> На корпусе документов ФПСР (Устав, Правила, Положение о членстве) c большим
> количеством **точных ссылок** (ФЗ № 7-ФЗ, § 21.3, «БЕКОСО», «МКПС»)
> dense-векторный поиск **проигрывает** sparse-поиску по recall: семантическая
> близость не помогает найти точные термины, которые редко появляются в обучающей
> выборке embedding-модели. Hybrid (dense + BM25 + Reciprocal Rank Fusion)
> должен поднять recall значительно.

---

## 3. Архитектура pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                      ИСХОДНЫЕ ДАННЫЕ                                  │
│  3 PDF: Положение о членстве (12с), Правила (145с), Картинка (1с)    │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
       ┌──────────┐   ┌──────────┐   ┌──────────┐
       │  pypdf   │   │ Document │   │Sentence  │
       │  parser  │ → │  Loader  │ → │Splitter  │
       └──────────┘   └──────────┘   │ chunk=512│
                                     └────┬─────┘
                                          │
              ┌───────────────────────────┴────────────────────────┐
              ▼                                                     ▼
    ┌─────────────────────┐                          ┌─────────────────────┐
    │ KNOWLEDGE GRAPH     │                          │ INGEST в Qdrant     │
    │ (Ragas Testset)     │                          │  - dense (bge-m3)    │
    │  - HeadlineExtractor│                          │  - sparse (BM25)     │
    │  - SummaryExtractor │                          │ → 2 коллекции:       │
    │  - NER, Themes,     │                          │   documents          │
    │    Keyphrases       │                          │   documents_hybrid   │
    │  - relationships:   │                          └──────────┬───────────┘
    │    cos/jaccard      │                                     │
    │  → kg.json          │                                     │
    └──────────┬──────────┘                                     │
               │                                                 │
               ▼                                                 │
    ┌──────────────────────┐                                    │
    │ TESTSET GENERATION   │                                    │
    │  Personas:            │                                    │
    │   - novice            │                                    │
    │   - instructor        │                                    │
    │   - lawyer            │                                    │
    │  Synthesizers:        │                                    │
    │   60% single-hop      │                                    │
    │   20% multi-hop abs   │                                    │
    │   20% multi-hop spec  │                                    │
    │  → 20 вопросов        │                                    │
    │  → testset_auto.json  │                                    │
    └──────────┬───────────┘                                    │
               │                                                 │
               └────────────┬───────────────────────────────────┘
                            ▼
              ┌─────────────────────────┐
              │     RAG ПРОГОН          │
              │ для каждого вопроса:    │
              │  - retrieve top-5       │
              │  - LLM генерирует ответ│
              │  → samples              │
              └───────────┬─────────────┘
                          │
                          ▼
              ┌─────────────────────────┐
              │     RAGAS EVALUATE      │
              │ Судья LLM оценивает    │
              │ каждую пару по 4 метрик:│
              │  - Faithfulness         │
              │  - Answer Relevancy     │
              │  - Context Precision    │
              │  - Context Recall       │
              └───────────┬─────────────┘
                          │
                          ▼
              ┌─────────────────────────┐
              │       MLFLOW            │
              │  params + metrics + CSV │
              │  http://localhost:5050  │
              └─────────────────────────┘
```

---

## 4. Инструменты и модели

### Стек

| Слой | Инструмент | Версия |
|---|---|---|
| Векторная БД | **Qdrant** | latest |
| RAG-фреймворк | **LlamaIndex** | 0.10+ |
| Eval-фреймворк | **Ragas** | 0.2.15 |
| Трекинг | **MLflow** | 3.14 |
| Sparse-векторы | **FastEmbed** (BM25) | latest |
| Локальный inference | **Ollama** (Docker) | latest |
| Внешний inference | **OpenRouter** (free tier) | API |

### Модели

| Роль | Модель | Провайдер | Зачем |
|---|---|---|---|
| **Embeddings** | `bge-m3` (1024-dim, мультиязычная) | Ollama (локально) | Dense-вектора для retrieval и KG |
| **Sparse encoder** | `Qdrant/bm25` (lexical, language-agnostic) | FastEmbed (локально) | BM25-вектора для hybrid |
| **KG builder** | `google/gemma-4-31b-it:free` | OpenRouter | Извлечение summary/entities/keyphrases |
| **Testset gen** | `google/gemma-4-31b-it:free` | OpenRouter | Генерация вопросов с personas |
| **RAG generator** | `nvidia/nemotron-3-super-120b-a12b:free` | OpenRouter | Отвечает на вопросы |
| **Ragas judge** | `google/gemma-4-31b-it:free` | OpenRouter | LLM-as-judge: 4 метрики |

### Параметры RAG

| Параметр | Значение |
|---|---|
| `chunk_size` | 512 токенов |
| `chunk_overlap` | 50 токенов |
| `top_k` | 5 |
| `similarity` | cosine (dense) |
| `fusion` | RRF (Reciprocal Rank Fusion) для hybrid |
| `LLM temperature` | 0.1 (RAG generator) / 0 (judge) |

---

## 5. Корпус

3 PDF-документа Федерации Практической Стрельбы России:

| Файл | Стр. | Чанков | Содержание |
|---|---|---|---|
| `Положение о членстве ОСОО ФПСР.pdf` | 12 | 31 | Условия приёма, права/обязанности, БЕКОСО, исключение |
| `Правила вида спорта практическая стрельба с 04.12.2025.pdf` | 145 | 385 | Регламент Минспорта РФ по дисциплинам МКПС |
| `кратко-о-процессе-вступления.pdf` | 1 | 2 | **PDF-инфографика** — текст не извлекается стандартно (custom-шрифт, требует OCR) |

**Итого:** 418 чанков, проиндексированы в Qdrant в двух коллекциях:
- `documents` — только dense (1024-dim)
- `documents_hybrid` — dense + sparse (BM25)

### Тестовый набор (Ragas TestsetGenerator)

20 авто-сгенерированных вопросов с **3 personas**:

| Persona | Описание | Стиль |
|---|---|---|
| **novice** | Новичок, узнал про стрельбу из YouTube | «слыш ты там по этому ФЗ № 114 че там написано» |
| **instructor** | Действующий инструктор ФПСР | Терминологичный, со ссылками на сроки |
| **lawyer** | Юрист ФПСР | Точные ссылки на ФЗ № 7, 82, 150, 329 |

**Distribution синтезаторов:**
- 60% single-hop (12 вопросов) — факт из одного чанка
- 20% multi-hop abstract (4 вопроса) — концепт через несколько чанков
- 20% multi-hop specific (4 вопроса) — сравнение/комбинация фактов

Сохранено в `backend/tests/eval/testset_auto.json`.

---

## 6. Метрики Ragas

| Метрика | Что измеряет | Reference нужен? |
|---|---|---|
| **Faithfulness** | Доля утверждений в ответе, подкреплённых retrieved_contexts → нет ли галлюцинаций | ✗ |
| **Answer Relevancy** | Cosine similarity между «обратно сгенерированным вопросом из ответа» и оригиналом | ✗ |
| **Context Precision (with ref)** | Доля retrieved chunks, реально содержащих info из reference → не приволок ли мусор | ✓ |
| **Context Recall** | Доля утверждений из reference, выводимых из retrieved_contexts → нашёл ли всё нужное | ✓ |

Все 4 — LLM-as-judge: судья на каждый Job делает 1–3 LLM-вызова с разбором.

---

## 7. Эксперимент

### Сценарий

1. Прогнать **20 вопросов** через RAG с **dense-only retrieval** → MLflow run №1.
2. Тот же набор вопросов через RAG с **hybrid retrieval** → MLflow run №2.
3. Сравнить run-ы side-by-side в MLflow UI.

Единственное отличие между run-ами — **retrieval mode**. Все остальные параметры
(generator, judge, chunker, embeddings, top_k, dataset) идентичны.

### Run-ы в MLflow

| Run | Mode | Status | run_id |
|---|---|---|---|
| `json-dense-nemotron-…-judge-gemma-…-k5` | dense | FINISHED | `4ca165905e5047369f3dd40ba380af6e` |
| `json-hybrid-nemotron-…-judge-gemma-…-k5` | hybrid | FINISHED | `92b32508b90d41b3bc257812d673a280` |

---

## 8. Результаты

### Средние метрики (по 20 вопросам)

| Метрика | Dense | Hybrid | Δ абсолютно | Δ относительно |
|---|---|---|---|---|
| **Faithfulness** | 0.826 | **1.000** | +0.174 | **+21%** |
| **Answer Relevancy** | 0.700 | **0.816** | +0.116 | **+17%** |
| **Context Precision** | 0.606 | **0.917** | +0.311 | **+51%** |
| **Context Recall** | 0.736 | **1.000** | +0.264 | **+36%** |

### Интерпретация по каждой метрике

**Context Recall: 0.736 → 1.000 (+36%)**
Самый большой прирост. Dense пропускал около четверти необходимой инфы — типично
для вопросов со ссылками на конкретные статьи и ФЗ. BM25 находит точные совпадения
терминов, а RRF-фьюжен поднимает их в топ-5 рядом с dense-релевантными.

**Context Precision: 0.606 → 0.917 (+51%)**
Самый большой относительный прирост. При dense-only retrieval **40% чанков в
top-5 были мусором** — это плохо влияло на LLM (галлюцинации, отвлечение).
Hybrid отсёк нерелевантные.

**Faithfulness: 0.826 → 1.000 (+21%)**
Когда контекст полный и без мусора, LLM не приходится «достраивать» из общих
знаний → нет галлюцинаций. Достигла **идеала 1.0** — все утверждения подкреплены.

**Answer Relevancy: 0.700 → 0.816 (+17%)**
Лучший контекст → точнее ответы по сути вопроса. Особенно заметно на multi-hop —
когда вопрос требует синтеза двух мест, dense-only часто давал ответ только на
половину вопроса.

### Файлы-артефакты

В каждом run-е MLflow:
- `eval_results_json.csv` — построчные оценки по каждому из 20 вопросов

Также подготовлены человекочитаемые версии:
- `backend/tests/eval/readable/eval_dense.xlsx`
- `backend/tests/eval/readable/eval_hybrid.xlsx`
- `backend/tests/eval/readable/compare_dense_vs_hybrid.xlsx` ← сравнение в одной таблице

---

## 9. Выводы

1. **Hybrid search должен быть включён по умолчанию** для этого корпуса.
   В прод-RAG (`backend/app/core/rag/retriever.py`) сейчас используется только dense.
   Стоит мигрировать на hybrid с BM25 — это самый дешёвый и эффективный
   улучшающий шаг.

2. **Ragas + MLflow — рабочая связка** для автоматической оценки RAG-итераций.
   Любое изменение в pipeline (новый chunker, другая embedding-модель, smarter
   retriever) теперь можно измерить тем же способом и сравнить в MLflow UI.

3. **Knowledge Graph + Persona-based testset generation** даёт честный тест:
   - 3 разных стиля задавания вопроса (новичок/инструктор/юрист) проверяют
     обобщающую способность retriever-а
   - Multi-hop вопросы заставляют синтезировать инфу из 2+ мест
   - Single-hop вопросы — baseline для базовой ситуации

4. **На корпусе с формальными ссылками** (ФЗ, статьи, нумерация, аббревиатуры)
   sparse-поиск **обязателен**. Семантические embedding-модели типа bge-m3
   плохо различают «ФЗ № 115» и «ФЗ № 150» — они близки по embedding-пространству.
   BM25 их легко разводит.

---

## 10. Ограничения и риски

### Методологические

- **Один LLM на 3 роли**: KG builder, testset gen и judge — все на `gemma-4-31b`.
  Та же модель писала эталоны и судила. **Чисто** должен быть judge другой
  семьи (Claude/GPT-4). Для следующей итерации стоит использовать платную
  Haiku 4.5 как judge — стабильнее и без bias.
- **Маленький тестовый набор**: 20 вопросов. Стат-значимость низкая. Стоит
  расширить до 50–100.
- **Картинка-PDF в индексе**: `кратко-о-процессе-вступления.pdf` парсится в
  кракозябры. BM25 цепляет эти токены и иногда подтягивает мусорные чанки.
  Лечится OCR (Tesseract / pdf2image), но в этой итерации не добавляли.

### Технические

- **Free-tier OpenRouter** имеет лимиты:
  - 20 RPM на провайдере (упирается часто)
  - 2000 запросов/день
  - Провайдеры периодически 500-ят
  Ragas нивелирует через `max_retries=3` и `raise_exceptions=False`, но
  отдельные Job-ы могут вылетать в NaN. Это шумит средние метрики.
- **Ollama на Mac** OOM-ит при попытке держать в памяти `qwen2.5:7b` + `bge-m3` +
  `qwen3:1.7b` одновременно. Решили — `num_ctx=8192` + последовательные модели.
- **Reasoning-модели как генератор** (qwen3) уходят в петлю «размышлений» на
  длинных промптах. На локальной Ollama давало timeout 10+ минут.

---

## 11. Дальнейшие шаги

### Краткосрочные

1. **Перенести hybrid в прод-код** (`backend/app/core/rag/retriever.py`):
   - `enable_hybrid=True` в `QdrantVectorStore`
   - Реиндексация существующих 418 чанков с sparse-векторами
   - Покрытие тестами

2. **Заменить судью на платную модель** (Claude Haiku 4.5 через OpenRouter,
   ~$0.10 на полный прогон). Уберёт шум и сделает оценки воспроизводимыми.

3. **OCR для картинок-PDF**: добавить `pytesseract` + `pdf2image` в DocumentLoader.
   Этот шаг важен — в реальном корпусе будут сканы.

### Среднесрочные

4. **Расширение датасета** до 50–100 вопросов через TestsetGenerator с большим
   `testset_size` + ручная курация (выкинуть кривые автогенерированные).

5. **Срезы метрик в MLflow** — мы уже логируем `by_synth__*`, можно добавить
   `by_persona__*` для срезов «как RAG отвечает novice vs lawyer».

6. **CI-интеграция**: GitHub Action, который при изменении в `app/core/rag/`
   запускает eval, и если метрики просели больше чем на X% — блокирует merge.

### Долгосрочные

7. **Prefect** для оркестрации:
   - Pipeline ingest (load → parse → chunk → embed → upsert) с retry и UI
   - Nightly eval-job на полном датасете
8. **Полный корпус ФПСР** (10 директорий с Яндекс-Диска) — после OCR и Prefect.
9. **Реальные user-вопросы** в качестве датасета вместо/в дополнение к
   авто-сгенерированному.

---

## 12. Артефакты эксперимента

### В репозитории

| Файл | Назначение |
|---|---|
| `backend/scripts/eval_rag.py` | Главный скрипт eval (с поддержкой dense/hybrid, openrouter/ollama) |
| `backend/scripts/generate_kg.py` | Построение knowledge graph |
| `backend/scripts/generate_testset.py` | Генерация датасета с personas |
| `backend/scripts/ingest_local.py` | Загрузка PDF в `documents` коллекцию |
| `backend/scripts/ingest_hybrid.py` | Загрузка PDF в `documents_hybrid` коллекцию |
| `backend/scripts/_hybrid_retriever.py` | `HybridQdrantRetriever` (dense + sparse + RRF) |
| `backend/tests/eval/kg.json` | Knowledge graph: 33 узла, 592 рёбер |
| `backend/tests/eval/testset_auto.json` | Тестовый датасет: 20 вопросов |
| `backend/tests/eval/samples_json_dense.json` | RAG-кэш для dense прогона |
| `backend/tests/eval/samples_json_hybrid.json` | RAG-кэш для hybrid прогона |
| `backend/tests/eval/readable/compare_dense_vs_hybrid.xlsx` | Сводная таблица сравнения |

### MLflow

- UI: `http://localhost:5050` (запускается через sidecar контейнер)
- Backend store: `backend/mlflow.db` (SQLite)
- Артефакты: `backend/mlruns/1/<run_id>/artifacts/`

### Документация

- `docs/plans/2026-06-28-ragas-mlflow-eval-status.md` — статус-файл с roadmap
- `docs/plans/2026-06-28-ragas-full-workflow.md` — теоретический гайд по Ragas
- `docs/plans/2026-06-29-ragas-experiment-report.md` ← **этот документ**

---

## 13. Слайды для презентации (черновик)

1. **Постановка задачи** — зачем оценивать RAG автоматически
2. **Что такое Ragas** — LLM-as-judge, 4 ключевые метрики
3. **Что такое MLflow** — трекинг экспериментов, сравнение run-ов
4. **Pipeline** — диаграмма из секции 3
5. **Корпус** — 3 PDF ФПСР, 418 чанков
6. **Knowledge Graph + Personas** — как Ragas генерирует тестовый набор
7. **Гипотеза** — hybrid должен помочь
8. **Результаты** — таблица сравнения 4 метрик с дельтами
9. **Главный график** — bar chart dense vs hybrid (можно сделать в Excel/Numbers)
10. **Демо в MLflow UI** — Compare-режим side-by-side
11. **Выводы** — hybrid обязателен, MLflow подходит для CI
12. **Дальнейшие шаги** — OCR, платный judge, Prefect, реальный корпус

---

## Контактная информация

- Репозиторий: `FAQ_RAG_llm_bot/`
- Ветка: `main`
- MLflow data: `backend/mlflow.db` + `backend/mlruns/`
