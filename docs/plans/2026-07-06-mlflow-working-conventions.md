# MLflow: рабочие конвенции + разбор Фаз 4-5 подробно

**Дата:** 2026-07-06
**Зачем:** во время работы с MLflow было непонятно — как называть прогоны, что
логировать, как потом ревьюить. Здесь — минимальные правила + best practices, чтобы
эксперименты были воспроизводимыми и читаемыми через месяц.

Основано на нашем опыте + best practices (ссылки внизу).

---

## Часть 1. Разбор Фазы 4 (Итерации) — что мы вообще крутим

Фаза 4 = систематический перебор параметров с замером. Что можно менять в RAG
и что каждое влияет:

| Что крутим | Диапазон | На что влияет | Метрика-индикатор |
|---|---|---|---|
| **chunk_size** | 256 / 512 / 1024 | Гранулярность контекста | context_precision/recall |
| **chunk_overlap** | 0 / 50 / 100 | Не режется ли смысл на границах | context_recall |
| **top_k** | 3 / 5 / 10 | Сколько чанков в контекст | recall ↑, precision ↓ с ростом |
| **retrieval** | dense / hybrid | Как ищем | precision, recall |
| **embedding** | bge-m3 / e5 / qwen3-emb | Качество векторов | всё retrieval |
| **reranker** | нет / bge-reranker / Cohere | Пересортировка top-N | precision (часто сильно ↑) |
| **промпт** | версии SYSTEM_PROMPT | Как LLM использует контекст | faithfulness, relevancy |
| **LLM-генератор** | qwen3 / nemotron / gpt-oss | Качество ответа | faithfulness, relevancy |

**Золотое правило Фазы 4:** меняешь **одну вещь за раз**. Поменял два параметра —
не знаешь который дал эффект. Каждый вариант = отдельный MLflow run.

---

## Часть 2. Как устроен MLflow (модель данных)

```
Experiment (контейнер под одну задачу, напр. "rag-eval")
 ├── Run 1  (один прогон/конфигурация)
 │    ├── params   — что задали (chunk_size=512, top_k=5, ...) — НЕИЗМЕНЯЕМЫ
 │    ├── metrics  — что измерили (faithfulness=0.9, ...) — числа
 │    ├── tags     — метки для фильтрации (retrieval=hybrid, git=abc123)
 │    └── artifacts— файлы (CSV результатов, графики, конфиг)
 ├── Run 2
 └── ...
```

**Разница params vs tags vs metrics — это ключ к порядку:**
- **params** — входные настройки эксперимента (числа/строки конфига). Фиксированы.
- **metrics** — то что посчитали (могут иметь историю по шагам). Числа.
- **tags** — метки для **поиска и группировки** (git-коммит, автор, цель, версия данных).

---

## Часть 3. Наши ошибки и как правильно

### ❌ Как было у нас (плохо)

```
Имя прогона: json-dense-nemotron-3-super-120b-a12b:free-judge-gpt-oss-120b:free-k5
```

Проблемы:
- Нечитаемо, длинно, двоеточия ломают глаз
- Вся инфа впихнута в имя → нельзя фильтровать/группировать
- Нет git-коммита → не воспроизвести
- Нет версии датасета → неясно на чём считали
- Нет пометки «зачем этот прогон» и вывода

### ✅ Как правильно

**Имя прогона — короткое и человекочитаемое.** Детали → в params и tags.

```
Имя:  dense-k5           (или: exp2-dense, hybrid-rerank)
```

**Всё остальное раскладываем по полочкам:**

```python
mlflow.set_experiment("rag-eval")          # контейнер под задачу

with mlflow.start_run(run_name="dense-k5"):
    # PARAMS — конфигурация (для воспроизведения)
    mlflow.log_params({
        "retrieval_mode": "dense",
        "generator_model": "nemotron-3-super-120b",
        "judge_model": "gpt-oss-120b",
        "embedding_model": "bge-m3",
        "chunk_size": 512,
        "top_k": 5,
        "dataset_size": 15,
    })
    # TAGS — для фильтрации и ревью
    mlflow.set_tags({
        "git_commit": "7b6b697",           # ← воспроизводимость!
        "dataset_version": "testset_v2",    # ← на чём считали
        "corpus": "fpsr-3docs-ocr",
        "author": "sasha",
        "purpose": "baseline dense для сравнения с hybrid",  # ← зачем
    })
    # METRICS — результаты
    mlflow.log_metric("mean_faithfulness", 0.909)
    # ... остальные
    # ARTIFACTS — файлы
    mlflow.log_artifact("eval_results.csv")
    # ВЫВОД — записываем прямо в описание прогона
    mlflow.set_tag("mlflow.note.content",
                   "Dense выигрывает 3/4 метрик. Recall 0.95. Вывод: baseline OK.")
```

Теперь в UI можно: фильтровать `tags.retrieval_mode = "hybrid"`, группировать по
`dataset_version`, найти прогон по `git_commit`, прочитать `purpose` и вывод.

---

## Часть 4. Минимальные правила (чек-лист для каждого прогона)

Прежде чем запустить eval — убедись что логируешь:

- [ ] **Короткое имя** прогона (`dense-k5`, не «простыня с двоеточиями»)
- [ ] **git_commit** в тегах (иначе не воспроизвести)
- [ ] **dataset_version** в тегах (на каком testset считали)
- [ ] **Все params** нужные для воспроизведения (модели, chunk_size, top_k)
- [ ] **purpose** в тегах — зачем этот прогон одной фразой
- [ ] **Метрики** с понятными именами (`mean_faithfulness`, а не `m1`)
- [ ] **CSV-артефакт** с поваршивочными результатами
- [ ] **Вывод** после прогона — в `mlflow.note.content` или в отчёте

**Правило ревью:** через месяц открываешь прогон и за 10 секунд понимаешь —
что запускали, на чём, зачем, и какой вывод. Если не понимаешь — конвенция нарушена.

---

## Часть 5. Организация экспериментов (best practices)

### Именование экспериментов (контейнеров)
- **Осмысленно, не generic.** `rag-eval-fpsr`, а не `test` / `my-experiment`.
- **По задаче/проекту:** `rag-eval`, `chunking-sweep`, `prompt-tuning`.

### Именование прогонов
- Короткое, отражает **отличие** этого прогона: `dense-k5`, `hybrid-k5`, `chunk256`.
- Дата/версия — в тегах, не в имени (MLflow сам пишет время).

### Parent/Child runs (для перебора)
Когда делаешь **свип** (например top_k = 3,5,10) — оформляй как родитель+дети:

```python
with mlflow.start_run(run_name="top_k-sweep") as parent:      # родитель
    for k in [3, 5, 10]:
        with mlflow.start_run(run_name=f"k{k}", nested=True):  # ребёнок
            ... eval с top_k=k ...
```

В UI свип сгруппируется — видно «это один эксперимент из 3 вариантов», а не 3
разрозненных прогона.

### Теги для фильтрации
Договорись о наборе тегов и **используй одинаковые везде**: `retrieval_mode`,
`judge_model`, `dataset_version`, `git_commit`, `author`, `purpose`. Тогда в UI
поиск `tags.retrieval_mode = "hybrid"` соберёт все нужные прогоны.

---

## Часть 6. Как ревьюить результаты в UI

1. **Список прогонов** — колонки настраиваются: вывести params + ключевые метрики
   рядом. Отсортировать по метрике.
2. **Фильтр** — по тегам (`tags.dataset_version = "testset_v2"`) чтобы сравнивать
   яблоки с яблоками (один датасет!).
3. **Compare** — выбрать 2+ прогона → кнопка Compare → parallel coordinates /
   таблица дельт (мы это использовали для dense vs hybrid).
4. **Artifacts** — открыть CSV конкретного прогона, посмотреть поваршивочно.
5. **Note** — прочитать вывод который записали после прогона.

**Важное правило сравнения:** сравнивай прогоны только на **одном и том же
датасете и судье**. Мы обожглись — сравнивать dense@gemma-judge с hybrid@gpt-judge
некорректно (разные условия). Меняем ОДНО.

---

## Часть 7. Что стоит внедрить в наш `eval_rag.py`

Сейчас скрипт логирует params и метрики, но **не логирует**:
- [ ] git-коммит в теги (`git rev-parse HEAD`)
- [ ] версию датасета в теги
- [ ] `purpose` (можно через env-переменную `RUN_PURPOSE`)
- [ ] короткое читаемое имя (сейчас длинная простыня)
- [ ] вывод в note (пишем руками после анализа)

→ это часть MLOps-линии (боль #2 версионирование). Оформить когда дойдём до DVC/CI.

---

## Итоговое минимальное правило (если запомнить только одно)

> **Имя прогона — короткое для человека. Всё для воспроизведения — в params.
> Всё для фильтрации и ревью — в tags (обязательно git_commit + dataset_version +
> purpose). Вывод — в note. Сравнивай только на одинаковых датасете+судье.**

---

## Источники (best practices)

- [Organizing MLflow Runs into Experiments (apxml)](https://apxml.com/courses/data-versioning-experiment-tracking/chapter-3-tracking-experiments-mlflow/organizing-mlflow-runs-experiments)
- [MLflow Experiment Tracking Best Practices (ML Journey)](https://mljourney.com/mlflow-experiment-tracking-best-practices/)
- [Understanding Parent and Child Runs (MLflow docs)](https://mlflow.org/docs/latest/traditional-ml/hyperparameter-tuning-with-child-runs/part1-child-runs/)
- [Organize training runs with MLflow experiments (Databricks)](https://docs.databricks.com/aws/en/mlflow/experiments)
- [Find your way to MLflow without confusion (Marvelous MLOps)](https://medium.com/marvelous-mlops/find-your-way-to-mlflow-without-confusion-d86bc710fc73)
- [5 Quick Tips to Improve Your MLflow Model Experimentation (TDS)](https://towardsdatascience.com/5-quick-tips-to-improve-your-mlflow-model-experimentation-dae346db825/)
