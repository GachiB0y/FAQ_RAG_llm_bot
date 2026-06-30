# Полный workflow Ragas на нашей RAG-системе

**Цель документа:** разобрать все ключевые возможности Ragas (knowledge graph,
персонажи, типы вопросов, метрики, трекинг в MLflow) на нашей конкретной RAG-системе
(qwen3:1.7b + bge-m3 + Qdrant + 3 PDF ФПСР). По итогу — понимать, что Ragas
умеет и как этим пользоваться вне учебных туториалов.

> Это **учебный гайд**, а не production-план. Цель — пощупать максимум возможностей,
> а не построить промышленный CI. Сравни с [этим status-файлом](2026-06-28-ragas-mlflow-eval-status.md)
> где описана продакшен-roadmap.

---

## 0. Архитектура Ragas в одной картинке

```
┌─────────────────────────────────────────────────────────────────────┐
│                          ИСХОДНЫЕ ДАННЫЕ                              │
│  3 PDF (Положение о членстве, Правила, Краткое-о-вступлении)         │
└──────────────────────────────────────┬──────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Этап 1: KNOWLEDGE GRAPH                                              │
│                                                                       │
│  Transforms (LLM-powered) над каждым чанком:                         │
│  ├─ HeadlinesExtractor    — заголовки/секции                         │
│  ├─ SummaryExtractor      — короткое summary                          │
│  ├─ NERExtractor          — именованные сущности                      │
│  ├─ KeyphrasesExtractor   — ключевые фразы                           │
│  ├─ EmbeddingExtractor    — эмбеддинг                                │
│  └─ ...                                                              │
│                                                                       │
│  Relationship builders — рёбра между узлами:                         │
│  ├─ CosineSimilarityBuilder    — семантическое сходство             │
│  ├─ JaccardSimilarityBuilder   — пересечение entities                │
│  └─ OverlapScoreBuilder         — общие keyphrases                   │
│                                                                       │
│  Результат: KnowledgeGraph с узлами (chunks) и взвешенными рёбрами  │
└──────────────────────────────────────┬──────────────────────────────┘
                                       │
                  ┌───────────────────┴────────────────────┐
                  ▼                                         ▼
┌─────────────────────────────┐         ┌────────────────────────────────┐
│ Этап 2: PERSONAS              │         │ Этап 3: QUERY SYNTHESIZERS     │
│                              │         │                                │
│ - "Новичок" — обывательский  │         │ Single-hop (60%):             │
│   язык                       │         │   Один узел графа → факт      │
│ - "Инструктор" — терминология│         │                                │
│ - "Юрист" — ссылки на ФЗ     │         │ Multi-hop abstract (20%):     │
│                              │         │   Несколько узлов → концепт   │
│                              │         │                                │
│                              │         │ Multi-hop specific (15%):     │
│                              │         │   Несколько узлов → сравнение │
│                              │         │                                │
│                              │         │ Reasoning / conditional (5%): │
│                              │         │   Вывод из правил             │
└──────────────────┬───────────┘         └─────────────┬──────────────────┘
                   │                                    │
                   └─────────────────┬─────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Этап 4: TESTSET GENERATION                                          │
│                                                                       │
│  TestsetGenerator(llm, embeddings, kg, personas)                     │
│   .generate(testset_size=30, query_distribution=[...])               │
│                                                                       │
│  Результат: 30 строк CSV/JSON:                                       │
│   - user_input            (вопрос от персонажа)                      │
│   - reference             (эталонный ответ из графа)                 │
│   - reference_contexts    (какие узлы ДОЛЖНЫ быть найдены)           │
│   - synthesizer_name      (тип: single/multi/reasoning)              │
│   - persona               (от чьего имени задавался)                 │
└──────────────────────────────────────┬──────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Этап 5: RAG RUN                                                      │
│                                                                       │
│  Для каждого вопроса:                                                │
│    answer, retrieved_contexts = our_rag.query(user_input)            │
│                                                                       │
│  Получаем EvaluationDataset:                                         │
│   {user_input, reference, response, retrieved_contexts}              │
└──────────────────────────────────────┬──────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Этап 6: EVALUATION                                                   │
│                                                                       │
│  ragas.evaluate(dataset, metrics=[                                    │
│    Faithfulness,                  ← нет ли галлюцинаций?              │
│    AnswerRelevancy,               ← релевантен ли ответ вопросу?      │
│    LLMContextPrecisionWithRef,    ← retriever приволок только нужное? │
│    LLMContextRecall,              ← retriever нашёл всё нужное?       │
│    AnswerCorrectness,             ← совпадает ли с эталоном?          │
│    AnswerSimilarity,              ← насколько по смыслу совпадает?    │
│  ])                                                                   │
└──────────────────────────────────────┬──────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Этап 7: MLFLOW                                                       │
│                                                                       │
│  Логируем как параметры:                                              │
│   - judge_model, generator_model, embedding_model, top_k             │
│   - testset_size, persona_count, query_distribution                  │
│   - chunk_size, similarity_threshold                                  │
│                                                                       │
│  Логируем как метрики:                                                │
│   - mean_faithfulness, mean_answer_relevancy и т.д.                  │
│   - В разрезе persona / synthesizer (через MLflow tags)              │
│                                                                       │
│  Артефакты: testset.json, kg.json, eval_results.csv                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 1. Knowledge Graph

### Что это

Граф, где **узлы — это чанки документов** (+ узлы-документы как «корни»), а **рёбра —
тематические связи**. Сам по себе граф не отвечает на вопросы — он нужен генератору
тестов, чтобы:

- понимать какие куски документов **близки по теме** → можно строить multi-hop вопросы;
- понимать какие **сущности повторяются** между документами → можно делать
  cross-document вопросы;
- выбирать какие узлы взять как «отправную точку» для генерации вопроса.

### Что внутри узла

Каждый узел графа после прогона transforms содержит:

| Поле | Что | Пример (из «Положения о членстве») |
|---|---|---|
| `page_content` | оригинальный текст чанка | «БЕКОСО — это курсы безопасного…» |
| `summary` | LLM-генерированное summary | «Описание курсов БЕКОСО для кандидатов» |
| `headlines` | заголовки/секции | `["V. ПОРЯДОК ВСТУПЛЕНИЯ", "21.1"]` |
| `entities` | NER-сущности | `["ФПСР", "БЕКОСО", "ipsc.ru"]` |
| `keyphrases` | ключевые фразы | `["курс безопасного обращения с оружием", "инструктор ФПСР"]` |
| `embedding` | вектор от bge-m3 | `[0.12, -0.34, …]` 1024-dim |

### Что внутри ребра

`Relationship(source=node_a, target=node_b, type=..., properties={...})`. Главные типы:

- `cosine_similarity` — векторы близки → семантически похожие чанки
- `jaccard_similarity_entities` — большое пересечение сущностей
- `overlap_score_keyphrases` — общие ключевые фразы

Каждое ребро имеет вес (score) и может быть направленным.

### Как мы будем его строить

В Ragas 0.2.x:

```python
from ragas.testset.graph import KnowledgeGraph, Node, NodeType
from ragas.testset.transforms import default_transforms, apply_transforms

# 1. Готовим узлы из наших чанков (либо из llama-index nodes, либо из langchain documents)
kg = KnowledgeGraph()
for chunk in our_chunks:
    kg.nodes.append(Node(
        type=NodeType.CHUNK,
        properties={"page_content": chunk.text, "document_metadata": chunk.metadata}
    ))

# 2. Прогоняем дефолтные трансформации (используют LLM!)
transforms = default_transforms(documents=langchain_docs, llm=judge_llm, embedding_model=judge_emb)
apply_transforms(kg, transforms)

# 3. Сохраняем граф
kg.save("backend/tests/eval/kg.json")
```

> **Внимание:** трансформации делают LLM-вызовы — на 418 чанков это **сотни вызовов**.
> Локально на qwen2.5:7b это очень долго. Для учебного примера возьмём подмножество:
> только «Положение о членстве» (31 чанк) — это уже даст ~50–100 LLM-вызовов на этапе KG.

### Что узнаем

- Какие документы «связаны» в нашем корпусе. Подсказка: в нашем корпусе только 3 файла,
  и кратко-о-вступлении парсится в кракозябры — он почти не свяжется ни с чем. Это можно
  будет увидеть на графе.
- Какие сущности фигурируют чаще всего — то ли это сущности, под которые мы хотим
  оптимизировать поиск.
- Сколько связных компонент — хорошие RAG-корпуса обычно один большой граф; если несколько
  изолированных кусков, это сигнал «темы плохо связаны, retriever будет на них слаб».

---

## 2. Personas (персонажи)

### Зачем

Один и тот же факт можно спросить десятью способами. Retriever работает плохо, когда
запрос сильно не похож на текст в документе (формулировки, сленг). Personas заставляют
генератор задавать **одинаковые по смыслу** вопросы **разными словами** — это
честная проверка обобщающей способности RAG.

### Наши 3 персонажа

```python
from ragas.testset.persona import Persona

personas = [
    Persona(
        name="novice",
        role_description=(
            "Новичок, никогда не стрелял из боевого оружия. Только что узнал "
            "про практическую стрельбу из YouTube. Языком — без терминов, "
            "по-простому. Часто использует разговорные формулировки: "
            "'как записаться', 'надо ли что-то сдавать', 'долго ли ждать'."
        ),
    ),
    Persona(
        name="instructor",
        role_description=(
            "Действующий инструктор ФПСР, ведёт курсы БЕКОСО. Знает термины, "
            "пользуется аббревиатурами (ФПСР, БЕКОСО, РСОО, МКПС). Интересуется "
            "процедурными деталями, сроками рассмотрения документов, ответственностью."
        ),
    ),
    Persona(
        name="lawyer",
        role_description=(
            "Юрист ФПСР, проверяет соответствие Положения федеральному "
            "законодательству. Задаёт вопросы со ссылками на ФЗ № 7, № 82, № 150, "
            "№ 329. Проверяет точные формулировки, ссылается на пункты и статьи."
        ),
    ),
]
```

### Эффект

Допустим, в документе написано: «Президент Федерации принимает решение о приёме».
Один и тот же факт три персонажа могут спросить так:

- **novice:** «А кто решает примут меня или нет?»
- **instructor:** «Кто компетентен принимать решение по заявке кандидата?»
- **lawyer:** «Каким должностным лицом ФПСР принимается решение о приёме в члены согласно п. 26 Положения?»

Все три ответа должны вести к одному. Если retriever проваливается на варианте novice
(потому что в документе нет слова «решает», есть «принимает решение») — это сигнал
к добавлению **query rewriting** или **hybrid search**.

---

## 3. Query Synthesizers (типы вопросов)

В Ragas 0.2.x есть несколько встроенных синтезаторов:

| Класс | Что делает | Сложность для RAG |
|---|---|---|
| `SingleHopSpecificQuerySynthesizer` | Берёт **один узел** графа, формирует конкретный фактический вопрос | Низкая — обычный lookup |
| `MultiHopAbstractQuerySynthesizer` | Берёт **2+ узла**, соединённых ребром, формирует **абстрактный/концептуальный** вопрос (требует синтеза) | Высокая — обычный RAG может провалиться, особенно если узлы из разных документов |
| `MultiHopSpecificQuerySynthesizer` | Берёт 2+ узла, формирует **конкретный** сравнительный/совместный вопрос | Высокая |

Distribution для нашего учебного прогона:

```python
query_distribution = [
    (SingleHopSpecificQuerySynthesizer(llm=judge_llm), 0.6),
    (MultiHopAbstractQuerySynthesizer(llm=judge_llm), 0.2),
    (MultiHopSpecificQuerySynthesizer(llm=judge_llm), 0.2),
]
# 60% простых, 40% сложных — норм для учебного эксперимента
```

### Reasoning queries — отдельный кейс

В Ragas 0.2.x **отдельного reasoning-синтезатора нет**, но reasoning «случается сам собой»
внутри multi-hop. Если нужны явные reasoning вопросы — придётся писать кастомный
синтезатор. Для учебного примера пропускаем.

---

## 4. Test set generation

### Сам код

```python
from ragas.testset import TestsetGenerator
from ragas.testset.synthesizers import (
    SingleHopSpecificQuerySynthesizer,
    MultiHopAbstractQuerySynthesizer,
    MultiHopSpecificQuerySynthesizer,
)

generator = TestsetGenerator(
    llm=judge_llm,           # тот же qwen2.5:7b или Haiku через OpenRouter
    embedding_model=judge_emb,
    knowledge_graph=kg,
    persona_list=personas,
)

testset = generator.generate(
    testset_size=30,
    query_distribution=[
        (SingleHopSpecificQuerySynthesizer(llm=judge_llm), 0.6),
        (MultiHopAbstractQuerySynthesizer(llm=judge_llm), 0.2),
        (MultiHopSpecificQuerySynthesizer(llm=judge_llm), 0.2),
    ],
)

testset.to_pandas().to_json(
    "backend/tests/eval/testset_auto.json", orient="records", force_ascii=False
)
```

### Что в результате

Pandas DataFrame с колонками:

| Колонка | Тип | Пример |
|---|---|---|
| `user_input` | str | «Какие документы нужно загрузить кандидату через личный кабинет на сайте?» |
| `reference` | str | «В личный кабинет кандидат загружает скан подписанного заявления (анкеты) на вступление в члены Федерации…» |
| `reference_contexts` | list[str] | `["…пункт 21.3 Положения…", "…подписание электронной подписью…"]` |
| `synthesizer_name` | str | `"single_hop_specifc_query_synthesizer"` |
| `persona` | dict | `{"name": "novice", "role_description": "…"}` |

### Сколько это стоит по времени

На наших данных:

- Только «Положение о членстве» (31 чанк): KG build ~50 LLM-вызовов = ~10–15 мин локально.
- Generation 30 вопросов: ещё ~60–90 LLM-вызовов = ~15–25 мин.
- **Итого подготовка датасета:** ~25–40 минут.

С Haiku/GPT-4o-mini через OpenRouter — те же шаги за **2–4 минуты**.

---

## 5. Evaluation: расширенный набор метрик

Сейчас в нашем `eval_rag.py` 4 метрики. На сгенерированном датасете имеет смысл
добавить ещё:

| Метрика | Что измеряет | Нужен reference? |
|---|---|---|
| `Faithfulness` | % утверждений ответа, поддержанных контекстом | ✗ |
| `AnswerRelevancy` | насколько ответ релевантен вопросу | ✗ |
| `LLMContextPrecisionWithReference` | retriever достал только нужное | ✓ |
| `LLMContextRecall` | retriever достал всё нужное | ✓ |
| `AnswerCorrectness` | насколько ответ совпадает с эталоном (комбо: factual+semantic) | ✓ |
| `AnswerSimilarity` | semantic-similarity между ответом и эталоном (через embeddings) | ✓ |
| `NoiseSensitivity` | как меняется качество при добавлении нерелевантных чанков | ✓ |

В Ragas 0.2.x все эти метрики есть «из коробки».

### Срезы (slices)

Главное преимущество автогенерированного датасета — **возможность делать срезы**.
Из MLflow:

- средний faithfulness **по персонажам** (новичок vs инструктор vs юрист)
- средний context_recall **по типу вопроса** (single vs multi-hop)
- средний answer_correctness **по документу-источнику**

Если novice проваливается на context_recall, а instructor нет — значит retriever
плохо понимает обывательские формулировки. Это конкретное знание для шага 3
(hybrid search) или для добавления query rewriting.

---

## 6. MLflow: что именно туда писать

### Параметры (log_param)

```
generator_model       qwen3:1.7b
embedding_model       bge-m3
judge_model           qwen2.5:7b
top_k                 5
similarity_threshold  0.5
chunk_size            512
chunk_overlap         50
testset_size          30
persona_count         3
distribution          {single_hop: 0.6, multi_hop_abs: 0.2, multi_hop_spec: 0.2}
corpus_files          3 (418 chunks)
```

### Метрики (log_metric)

- `mean_faithfulness`, `mean_answer_relevancy`, …
- `mean_faithfulness__persona_novice`, `mean_faithfulness__persona_instructor` (с MLflow tags)
- `mean_context_recall__synthesizer_single_hop`, и т.д.

### Артефакты (log_artifact)

- `kg.json` — knowledge graph (~5–20 MB после трансформов)
- `testset.json` — сгенерированный датасет
- `eval_results.csv` — pandas df со всеми оценками по каждой паре
- `kg_visualization.html` — опционально, если используем `kg.to_graphviz()` или D3.js viz

### Сравнение прогонов

В MLflow UI: открываем оба run (manual + auto), нажимаем **Compare** — получаем
таблицу-разницу. Это «настоящий» MLflow в действии — то, ради чего его и стоит
использовать.

---

## 7. Файловая структура (после реализации)

```
backend/
├── scripts/
│   ├── ingest_local.py            ← готово
│   ├── eval_rag.py                ← готово (manual dataset)
│   ├── generate_kg.py             ← новое: строит KG
│   └── generate_testset.py        ← новое: использует KG + personas + synthesizers
└── tests/
    └── eval/
        ├── golden_manual.json     ← ручные 10 вопросов
        ├── kg.json                ← knowledge graph
        ├── testset_auto.json      ← сгенерированные 30 вопросов
        └── eval_results_*.csv     ← результаты прогонов
```

---

## 8. План реализации (поэтапно)

1. **(идёт)** baseline-прогон ручных 10 вопросов → MLflow run #1.
2. Написать `generate_kg.py`, прогнать на «Положении о членстве». **Проверить:**
   - сколько узлов получилось (~31)
   - сколько рёбер (ожидаем десятки)
   - какие топ-10 keyphrases (должны включать «ФПСР», «БЕКОСО», «Президент», …)
3. Написать `generate_testset.py` с 3 personas, 30 вопросами. **Проверить глазами:**
   - вопросы правильно «звучат» по персонажу?
   - reference адекватный?
   - multi-hop реально требует 2+ источников?
4. Прогнать тот же `eval_rag.py` (с минимальной адаптацией: загружать из JSON, не из inline) →
   MLflow run #2. Добавить метрики `AnswerCorrectness`, `AnswerSimilarity`.
5. Открыть MLflow UI, сравнить run #1 vs run #2. Записать наблюдения.
6. **Сделать срезы:** написать `analyze_results.py` который читает `eval_results.csv`,
   группирует по persona/synthesizer, выводит summary-таблицу.

---

## 9. Что мы изучим по итогам

- Как Ragas строит knowledge graph и для чего он на самом деле нужен.
- Как работают persona-based генераторы и почему это улучшает покрытие.
- Разницу single-hop / multi-hop вопросов и какое влияние они оказывают на метрики.
- Как читать ragas-метрики в разрезах (по persona, по типу вопроса).
- Как сравнивать конфигурации RAG в MLflow.
- **Главное:** где наш RAG на qwen3:1.7b + bge-m3 + top_k=5 проваливается, и какие
  конкретно изменения (hybrid search, query rewriting, больший top_k, лучший LLM)
  стоит ставить первыми в очередь.

---

## 10. Возможные сюрпризы и подводные камни

- **qwen2.5:7b как judge на multi-hop вопросах будет шуметь.** Multi-hop требует
  логически последовательного разбора — слабым моделям это даётся плохо. Если оценки
  выглядят нелогично — это, скорее всего, не RAG плохой, а судья. Решение — переключить
  judge на Haiku/GPT-4o-mini через OpenRouter (мы это уже обсуждали).
- **TestsetGenerator может зацикливаться на одной теме.** Если граф несбалансированный,
  60% вопросов окажутся про одно и то же. Лечится подкручиванием `node_filter` в
  синтезаторах или явной балансировкой по `headlines`.
- **Default transforms на русском не идеальны.** NER и keyphrase-extraction обучены
  больше на английском. Может потребоваться кастомные prompts.
- **«кратко-о-вступлении.pdf» (PDF-картинка) в graph даст мусорный узел.** Стоит его
  отфильтровать ДО построения графа.
