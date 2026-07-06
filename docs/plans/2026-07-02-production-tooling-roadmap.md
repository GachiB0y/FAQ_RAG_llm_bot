# Production-tooling roadmap: что пощупать для прод-уровня

**Дата:** 2026-07-02
**Зачем:** проект сейчас на «учебном» стеке (Ollama, ручной MLflow, наивный RAG).
Ниже — 4 инструмента, которые двигают проект к тому, как реально делают в проде
в 2026 году. Каждый пункт — с конкретными шагами «потрогать руками», чтобы не
осталось просто теорией.

> Важно про TensorFlow Serving: **для LLM/RAG его НЕ используют.** TF Serving жив,
> но это про классический ML (TF SavedModels). Для LLM-инференса стек совсем другой
> (vLLM/SGLang) — см. пункт 2.

---

## Приоритет 1 — Langfuse (LLM observability) ⭐ самый полезный

**Что это:** опенсорс self-hosted платформа для трейсинга LLM-приложений. Логирует
КАЖДЫЙ запрос юзера: промпт → retrieval → LLM-ответ → latency → стоимость → токены.
Плюс встроенный eval, prompt-менеджмент, датасеты. Прямое **продолжение** того, что
мы делали с MLflow, но заточено под прод-мониторинг (не батч-эксперименты).

**Почему первый:** ближе всего к тому, что уже освоено. MLflow = «эксперименты
оффлайн», Langfuse = «наблюдение за живой системой».

**Что пощупать:**
- [ ] Поднять Langfuse через docker-compose (у них готовый `docker-compose.yml`)
- [ ] Обернуть RAGEngine.query() в `@observe()` декоратор Langfuse
- [ ] Сделать 5-10 запросов к чату → увидеть трейсы в UI (каждый шаг retrieval + generation)
- [ ] Посмотреть latency-разбивку: сколько на retrieval, сколько на LLM
- [ ] Настроить online-eval: Langfuse сам прогоняет faithfulness на проде
- [ ] Сравнить UX с MLflow — что удобнее для чего

**Ссылки:**
- https://langfuse.com/
- https://langfuse.com/self-hosting/docker-compose

---

## Приоритет 2 — vLLM (production LLM serving)

**Что это:** де-факто стандарт для self-hosted LLM-инференса. PagedAttention +
continuous batching → в разы больше throughput чем Ollama. OpenAI-совместимый API.

**Почему важно:** Ollama = отлично для dev/demo, но в проде задыхается (нет
батчинга, низкий throughput). Понять разницу — ключевой прод-навык.

**Что пощупать:**
- [ ] Запустить vLLM с маленькой моделью (`Qwen2.5-1.5B` или похожую), даже на CPU
      можно для теста — `vllm serve <model>`
- [ ] vLLM даёт OpenAI-совместимый endpoint → подключить его в наш `OllamaAdapter`-стиле
      адаптер (сделать `VLLMAdapter` или использовать существующий OpenAI-адаптер
      с `base_url`)
- [ ] Прогнать тот же eval (`eval_rag.py`) с генератором через vLLM
- [ ] Сравнить throughput: 10 параллельных запросов через Ollama vs vLLM
- [ ] Понять concept: continuous batching, KV-cache, PagedAttention

**Альтернативы для сравнения:** SGLang (быстрее на structured output), TGI (HF-стек).

**Ссылки:**
- https://docs.vllm.ai/
- https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html

---

## Приоритет 3 — LangGraph (agentic RAG) 🔮 главный тренд 2025-2026

**Что это:** граф-оркестрация LLM-агентов с состоянием. Главный сдвиг индустрии:
от «наивного RAG» (запрос → retrieve → generate) к «agentic RAG» — агент САМ
решает искать ли, переписывает запрос, делает несколько поисков, проверяет свой
ответ, вызывает tools.

**Почему важно:** это фронтир. Наш проект — классический наивный RAG (нормальная
основа), а современные системы — агентные с self-reflection.

**Что пощупать:**
- [ ] Изучить базовый LangGraph-граф: nodes (retrieve, grade, generate, rewrite)
      + edges (условные переходы)
- [ ] Построить **Self-RAG** или **Corrective RAG (CRAG)** поверх нашего Qdrant:
  - node «retrieve» — достаёт чанки
  - node «grade documents» — LLM оценивает релевантны ли чанки
  - если нерелевантны → node «rewrite query» → повторный retrieve
  - node «generate» → node «check hallucination» → если галлюцинация → regenerate
- [ ] Прогнать наш testset через agentic-версию → сравнить метрики с наивным RAG
      в MLflow (ещё один run!)
- [ ] Понять concept: state, conditional edges, cycles, checkpointing

**Гипотеза для проверки:** agentic RAG должен поднять faithfulness (self-check
ловит галлюцинации) ценой latency (несколько LLM-вызовов на запрос).

**Ссылки:**
- https://langchain-ai.github.io/langgraph/
- https://langchain-ai.github.io/langgraph/tutorials/rag/langgraph_self_rag/
- CRAG paper: https://arxiv.org/abs/2401.15884

---

## Приоритет 4 — pgvector (нужна ли отдельная векторка?)

**Что это:** расширение Postgres для векторного поиска. Тренд 2025-2026: «не плоди
новую БД — используй Postgres который уже есть». У нас Postgres уже стоит для
users/chats/docs.

**Почему важно:** архитектурное решение. Отдельная векторка (Qdrant) оправдана на
масштабе, но для многих проектов pgvector достаточно → меньше инфраструктуры.

**Что пощупать:**
- [ ] Добавить расширение `pgvector` в наш Postgres (`CREATE EXTENSION vector`)
- [ ] Создать таблицу с `vector(1024)` колонкой (bge-m3 dim)
- [ ] Загрузить те же 418 чанков туда
- [ ] Сделать `PgVectorRetriever` (аналог `QdrantRetriever`)
- [ ] Прогнать eval → сравнить с Qdrant (метрики + скорость)
- [ ] Понять когда pgvector достаточно, а когда нужен Qdrant (индекс HNSW,
      фильтры, масштаб)
- [ ] Бонус: `pgvectorscale` (расширение от Timescale) — ускоряет pgvector

**Ссылки:**
- https://github.com/pgvector/pgvector
- https://github.com/timescale/pgvectorscale

---

## Сводная таблица: текущий стек → прод-стек 2026

| Слой | Сейчас (учебный) | Прод 2026 | Приоритет пощупать |
|---|---|---|---|
| LLM serving | Ollama | **vLLM** / SGLang / managed API | 2 |
| Vector DB | Qdrant ✓ | Qdrant / **pgvector** / Milvus | 4 |
| RAG orchestration | LlamaIndex ✓ | LlamaIndex / **LangGraph** (agentic) | 3 |
| Offline eval | Ragas + MLflow ✓ | Ragas + MLflow / DeepEval | (сделано) |
| Online observability | — | **Langfuse** / LangSmith / Phoenix | 1 |
| Pipeline orchestration | — (синхронный ingest) | Prefect / Dagster | (в roadmap) |
| Embeddings | bge-m3 ✓ | bge-m3 / Qwen3-Embedding / Voyage | (ок) |

## Главный сдвиг индустрии 2025 → 2026

**От наивного RAG к agentic RAG.**
- Было: `запрос → retrieve top-5 → generate`
- Стало: агент сам решает искать ли, переписывает запрос, делает несколько поисков,
  проверяет ответ, вызывает tools, переспрашивает при неуверенности

Пункт 3 (LangGraph) — прямое погружение в этот тренд.

---

## Порядок прохождения (рекомендую)

1. **Langfuse** — быстро, полезно, продолжает MLflow-тему. 1-2 вечера.
2. **LangGraph agentic RAG** — самое интересное и трендовое. Прогнать через наш
   же eval → увидеть в MLflow улучшил ли agentic подход метрики. 2-3 вечера.
3. **vLLM** — если будет доступ к GPU (на CPU только «пощупать» concept). 1 вечер.
4. **pgvector** — архитектурный эксперимент, быстрый. 1 вечер.

Каждый пункт можно оформить как отдельный MLflow-run и добавить в наш
сравнительный отчёт — тогда получится полная картина «как разные прод-решения
влияют на метрики нашего RAG».
