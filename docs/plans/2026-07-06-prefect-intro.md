# Prefect — вводная (что, как, зачем нам) перед реализацией

**Дата:** 2026-07-06
**Зачем этот документ:** понять инструмент ДО того как писать код. Что такое
Prefect, как он работает, как мы хотим его настроить под наш пайплайн, с примерами.

---

## 1. Что это в одном предложении

**Prefect — это оркестратор:** он запускает многошаговые пайплайны, следит за
порядком шагов, повторяет упавшие, ведёт по расписанию и показывает всё в UI.

Аналогия: если обычный Python-скрипт — это «повар готовит по памяти», то Prefect —
это «кухня с чек-листом, таймерами и журналом: что готово, что подгорело, что
переделать».

## 1.1. Бесплатный или платный? (важно — легко запутаться)

Prefect бывает в двух видах:

| Вариант | Что | Цена |
|---|---|---|
| **Prefect (OSS)** | `pip install prefect` + `prefect server start` (UI локально) | **бесплатно** (Apache 2.0) |
| **Prefect Cloud** | их managed-хостинг + командные фичи + SLA | платно (страница prefect.io/pricing) |

**Мы используем ТОЛЬКО OSS-версию** — локальный server, ноль затрат. Страница цен
на сайте — это про Cloud, который нам не нужен. Аналогия: MLflow локально (как у
нас) бесплатно vs MLflow на Databricks платно. Ядро открыто.

---

## 2. Зачем он НАМ конкретно

Вспомни нашу боль на eval-прогонах:
- OpenRouter кидал **429** → скрипт падал → я **вручную** рестартовал
- Сидел и следил через мониторы «дошло/не дошло»
- Если падало на шаге 3 из 4 — начинали заново

Prefect это убирает:
| Наша боль | Как Prefect лечит |
|---|---|
| 429 → ручной рестарт | `@task(retries=5)` — сам ждёт и повторяет |
| Слежу за прогоном руками | UI показывает статус каждого шага |
| Падение = начать сначала | Recovery — продолжает с упавшего шага |
| «Надо не забыть прогнать eval» | Расписание — гоняет сам ночью |

---

## 3. Три главных понятия (вся модель Prefect)

### `@task` — один шаг работы
Обычная Python-функция с декоратором. Prefect её отслеживает, ретраит, логирует.

```python
from prefect import task

@task(retries=5, retry_delay_seconds=60)   # ← магия: повтор при падении
def run_eval(dataset: str) -> dict:
    # тут наш обычный вызов eval_rag
    return {"faithfulness": 0.9}
```

### `@flow` — пайплайн из шагов
Функция, которая вызывает tasks в нужном порядке. Prefect строит граф зависимостей.

```python
from prefect import flow

@flow(name="rag-eval-pipeline")
def rag_eval_pipeline():
    ingest()                        # шаг 1
    kg = build_kg()                 # шаг 2 (после ingest)
    testset = gen_testset(kg)       # шаг 3 (нужен kg)
    result = run_eval(testset)      # шаг 4 (нужен testset)
    return result
```

### Deployment — как это запускать/планировать
Регистрируешь flow → можешь запускать по кнопке, по API или **по расписанию**.

```bash
prefect deployment run "rag-eval-pipeline/nightly"   # запуск
# или расписание: каждый день в 3:00
```

---

## 4. Как retry реально работает (главное для нас)

```python
@task(retries=5, retry_delay_seconds=60)
def call_judge(question):
    resp = openrouter.chat(...)     # если 429 → исключение
    return resp                      # Prefect ловит, ждёт 60с, повторяет (до 5 раз)
```

Логика Prefect:
1. Task упал с исключением (429) → Prefect **не роняет весь flow**
2. Ждёт `retry_delay_seconds`
3. Повторяет. До `retries` раз.
4. Если все попытки исчерпаны → помечает task failed, но остальное что можно —
   доделывает.

**Именно это спасло бы нас** на прогонах где мы вручную рестартовали.

---

## 5. Как мы хотим настроить (план под наш проект)

Оборачиваем существующие скрипты (`ingest_local.py`, `generate_kg.py`,
`generate_testset.py`, `eval_rag.py`) в один flow:

```python
# backend/flows/rag_eval_flow.py  (примерный вид)
from prefect import flow, task
import subprocess

def _run(script, **env):
    # обёртка над нашим docker exec / python scripts/...
    ...

@task(retries=2, retry_delay_seconds=30)
def ingest():           _run("ingest_local.py")

@task(retries=2, retry_delay_seconds=30)
def build_kg():         _run("generate_kg.py")

@task(retries=3, retry_delay_seconds=60)   # KG жрёт много API → больше ретраев
def gen_testset():      _run("generate_testset.py")

@task(retries=5, retry_delay_seconds=90)   # eval = много 429 → максимум ретраев
def run_eval(mode):     _run("eval_rag.py", HYBRID=str(mode == "hybrid"))

@flow(name="rag-eval-pipeline")
def rag_eval_pipeline(retrieval_mode: str = "dense"):
    ingest()
    build_kg()
    gen_testset()
    run_eval(retrieval_mode)
```

Запуск:
```bash
python -m backend.flows.rag_eval_flow          # разово
prefect server start                            # поднять UI (localhost:4200)
```

**Настройки retry по шагам** (наша специфика — разное кол-во API-вызовов):
- ingest — 2 (локальные embeddings, редко падает)
- kg / testset — 3 (внешний API, средне)
- eval — 5 (много вызовов судьи → чаще 429)

---

## 6. Как это выглядит в UI

Prefect UI (`localhost:4200`) показывает:
- **Граф flow** — 4 квадрата (ingest→kg→testset→eval) со стрелками
- **Статус** каждого — зелёный/жёлтый(retry)/красный
- **Логи** каждого шага
- **История** прогонов — когда, сколько шёл, чем кончился

Похоже на MLflow, но MLflow про «метрики экспериментов», а Prefect про
«здоровье пайплайна» (что упало, что переретраилось).

---

## 7. Prefect vs то что у нас уже есть

| Инструмент | Отвечает на вопрос |
|---|---|
| **Makefile** (Шаг B) | «как запустить одной командой» |
| **Prefect** (Шаг F) | «как запустить с retry, по расписанию, с UI-мониторингом» |
| **MLflow** | «какие метрики дал прогон» |
| **Langfuse** | «что происходит с каждым запросом в проде» |

Не конкуренты — разные слои. Prefect идёт **поверх** Makefile: Makefile для
локального «прогнать сейчас», Prefect для «прогонять надёжно и по расписанию».

---

## 8. Чего НЕ будем делать (чтобы не усложнять)

- Не поднимаем Prefect Cloud — только локальный `prefect server`
- Не делаем сложные deployment с воркер-пулами — для pet-проекта избыточно
- Не переносим ВСЁ в Prefect — только eval-пайплайн, где реально болит retry

---

## Итог: что попробуем на реализации

1. Установить prefect
2. Обернуть 4 наших скрипта в `@task` + собрать `@flow`
3. Поставить retry на eval (главная польза — авто-повтор 429)
4. Поднять UI, прогнать flow, посмотреть граф
5. (опц.) расписание nightly

**Что вынесем:** поймём оркестрацию на своём пайплайне + получим избавление от
ручных рестартов на следующих eval-прогонах.
