# Production Infrastructure Design — FAQ RAG Bot

**Дата:** 2026-03-02
**Статус:** Утверждён
**Аудитория:** 1 000 пользователей, пики 200–300 одновременных

---

## Исходные параметры

| Параметр | Значение |
|----------|---------|
| Пользователей всего | 1 000 |
| Одновременных (пик) | 200–300 |
| Запросов/день | ~60 000 |
| Запросов/месяц | ~1 800 000 |
| Токенов на запрос (вход) | ~1 000 |
| Токенов на запрос (выход) | ~300 |
| Язык документов и вопросов | Русский |

---

## Архитектура

### Общая схема

```
Internet → CloudFlare (DDoS + SSL)
         → ALB (L7 балансировщик)
         → ECS Fargate Backend (2–8 pods, stateless, auto-scaling)
               ├── PostgreSQL RDS   (пользователи, документы, логи чатов)
               ├── Redis ElastiCache (сессии, rate limiting, task queue)
               ├── Qdrant           (векторные эмбеддинги документов)
               └── GPU Server       (vLLM + infinity-embedding)
```

### Ключевые принципы

- **Backend stateless** — горизонтально масштабируется без shared state
- **Redis** выполняет три роли: сессии, rate limiting (100 req/min/user), task queue для LLM
- **vLLM** вместо Ollama — continuous batching, 4× throughput при параллельных запросах
- **infinity-embedding** вместо Ollama для эмбеддингов — специализирован, быстрее

### Жизненный цикл запроса

```
1. Пользователь отправляет вопрос
2. Backend проверяет rate limit (Redis)
3. infinity-embedding векторизует вопрос (~50ms)
4. Qdrant ищет топ-5 релевантных чанков (~10ms)
5. Задача попадает в Redis Queue
6. vLLM Worker забирает задачу (continuous batching с другими запросами)
7. Токены стримятся клиенту через SSE
8. Вопрос/ответ/источники сохраняются в PostgreSQL
```

---

## Три стадии развёртывания

### Стадия 1 — Старт (месяц 0–6): Full Cloud API

**Когда переходить:** при появлении первых реальных пользователей или необходимости SLA.

**Стек:**
- LLM: **GPT-4o-mini** (OpenAI API) или **Gemini 2.0 Flash** (дешевле)
- Embedding: **text-embedding-3-small** (OpenAI API)
- Инфра: ECS Fargate + RDS + ElastiCache + EC2 для Qdrant

**Конфиг:**
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
```

**Стоимость (GPT-4o-mini):**

| Статья | $/мес |
|--------|-------|
| OpenAI LLM API | $594 |
| OpenAI Embedding API | $4 |
| ECS Fargate (2 tasks) | $50 |
| RDS PostgreSQL (primary + replica) | $100 |
| ElastiCache Redis | $17 |
| EC2 t3.large (Qdrant) | $60 |
| ALB + S3 + CloudWatch | $43 |
| **Итого** | **~$868/мес (~78 000 ₽)** |

**Альтернатива — Gemini 2.0 Flash** (в 2× дешевле):

| | GPT-4o-mini | Gemini 2.0 Flash |
|-|-------------|-----------------|
| Input /1M | $0.15 | $0.075 |
| Output /1M | $0.60 | $0.30 |
| LLM API/мес | $594 | $297 |
| **Итого** | **$868** | **$571** |

Gemini имеет OpenAI-совместимый API — код не меняется, только `OPENAI_BASE_URL`.

---

### Стадия 2 — Рост (месяц 6–18): Self-hosted GPU на RunPod

**Когда переходить:** расходы на API > $600/мес или > 500 активных пользователей.

**Стек:**
- LLM: **Qwen2.5-7B-Instruct** через **vLLM** на RunPod A10G
- Embedding: **bge-m3** через **infinity-embedding** (CPU)
- Инфра: ECS Fargate + RDS + ElastiCache + EC2 (Qdrant) + RunPod GPU

**Конфиг:**
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=fake-key
OPENAI_BASE_URL=https://your-pod-id-8001.proxy.runpod.net/v1
OPENAI_MODEL=Qwen/Qwen2.5-7B-Instruct
EMBEDDING_PROVIDER=infinity
EMBEDDING_URL=https://your-pod-id-7997.proxy.runpod.net
EMBEDDING_MODEL=BAAI/bge-m3
```

**Стоимость:**

| Статья | $/мес |
|--------|-------|
| RunPod A10G ($0.39/hr) | $281 |
| ECS Fargate | $50 |
| RDS (primary + replica) | $100 |
| ElastiCache Redis | $17 |
| EC2 t3.large (Qdrant) | $60 |
| ALB + S3 + CloudWatch | $43 |
| **Итого** | **~$551/мес (~50 000 ₽)** |
| **Экономия vs Стадия 1** | **-$317/мес (-36%)** |

**Производительность vLLM vs Ollama на A10G:**

| | Ollama | vLLM |
|-|--------|------|
| Параллельных запросов | 1–2 | 8–16 |
| Throughput | 5–8 req/sec | 20–40 req/sec |
| Ожидание 300-го в очереди | ~60 сек | ~10–15 сек |

---

### Стадия 3 — Зрелость (18+ мес): AWS Reserved Instances

**Когда переходить:** нагрузка стабильна, RunPod не устраивает по SLA.

**Стек:**
- LLM: **Qwen2.5-7B** через **vLLM** на EC2 g5.xlarge (reserved 1yr)
- Embedding: **bge-m3** через **infinity** на том же сервере (CPU)
- Инфра: всё на AWS Reserved Instances

**Стоимость (1yr reserved):**

| Статья | $/мес |
|--------|-------|
| EC2 g5.xlarge reserved (A10G) | $362 |
| ECS Fargate | $50 |
| RDS reserved | $50 |
| ElastiCache reserved | $10 |
| EC2 t3.large Qdrant | $40 |
| ALB + S3 + CloudWatch | $43 |
| **Итого** | **~$555/мес (~50 000 ₽)** |

---

## Сравнительная таблица

| | Стадия 1 (API) | Стадия 2 (RunPod) | Стадия 3 (AWS reserved) |
|--|---------------|------------------|------------------------|
| $/мес | $868 | $551 | $555 |
| $/год | $10 416 | $6 612 | $6 660 |
| Данные | Уходят в OpenAI | RunPod (EU) | Только AWS |
| SLA LLM | 99.9% OpenAI | ~99% RunPod | 99.9% AWS |
| DevOps сложность | Низкая | Средняя | Средняя |
| Время старта | 1–2 дня | 3–5 дней | 1 неделя |
| Breakeven vs API | — | Сразу дешевле | После 12 мес |

---

## LLM провайдеры — полный список вариантов

### Облачные API (OpenAI-совместимые, код не меняется)

| Провайдер | Модель | Input /1M | Output /1M | Примечание |
|-----------|--------|-----------|-----------|------------|
| OpenAI | gpt-4o-mini | $0.15 | $0.60 | Лучший баланс |
| Google | gemini-2.0-flash | $0.075 | $0.30 | Самый дешёвый |
| Mistral | mistral-small | $0.10 | $0.30 | Хорош на русском |
| Groq | llama-3.3-70b | $0.59 | $0.79 | Очень быстрый |
| Together AI | qwen2.5-7b | $0.20 | $0.20 | Managed open-source |
| AWS Bedrock | claude-haiku-3.5 | $0.80 | $4.00 | Данные в AWS |
| Azure OpenAI | gpt-4o-mini | $0.15 | $0.60 | Данные в Azure, GDPR |
| Yandex Cloud | YandexGPT Pro | ₽/токен | ₽/токен | Данные в России |

### Self-hosted (HuggingFace → vLLM)

| Модель | VRAM (4-bit) | Русский | Throughput |
|--------|-------------|---------|-----------|
| Qwen2.5-7B-Instruct | ~6GB | Отлично | Высокий |
| Qwen2.5-14B-Instruct | ~10GB | Очень хорошо | Средний |
| Gemma 3 9B | ~7GB | Хорошо | Высокий |
| Mistral 7B v0.3 | ~5GB | Хорошо | Высокий |
| Llama 3.3 70B | ~40GB | Хорошо | Низкий |

---

## Очередь задач: Redis vs Kafka

**Выбор: Redis (arq)** — обоснование:

- Нагрузка: 60 000 req/день = 0.7 msg/сек (пик ~5–8 msg/сек)
- Redis уже в стеке для сессий и rate limiting
- Kafka оправдана от сотен тысяч msg/сек и fan-out к нескольким консьюмерам
- Добавление Kafka: +$150–200/мес и отдельный брокер

**Надёжность Redis:**
- AOF persistence (`appendonly yes`, `appendfsync everysec`) — потеря max 1 сек при сбое
- ElastiCache с Multi-AZ репликой — failover за ~30 сек
- Идемпотентные задачи с `task_id` — защита от дублей при failover

---

## CI/CD Pipeline

```
Push → GitHub Actions:
  1. Lint (ruff) + Types (mypy)  ~1 мин
  2. Tests (pytest)               ~3 мин
  3. Build + Push → ECR           ~5 мин
  4. Deploy Staging (авто, main branch)
  5. Deploy Production (ручной approve, tag v*.*.*)
```

**Zero-downtime:** ECS rolling update — новые pods поднимаются до остановки старых.

---

## Мониторинг

**Стек:** Prometheus + Grafana + CloudWatch Logs

**Ключевые метрики:**

| Метрика | Предупреждение | Критично |
|---------|---------------|---------|
| LLM queue depth | > 50 задач | > 200 задач |
| p95 response latency | > 30 сек | > 60 сек |
| Error rate | > 5% | > 10% |
| GPU VRAM utilization | > 80% | > 90% |
| "Не нашёл ответа" % | > 30% | > 50% |

**Бизнес-метрики в PostgreSQL:**
- Запросов/день, запросов/пользователь
- Средний confidence score
- Топ вопросов без ответа → сигнал для пополнения базы документов

---

## Чеклисты миграции

### Стадия 1 → 2 (переход на RunPod vLLM)

```
□ Завести аккаунт RunPod
□ Запустить Pod с шаблоном vLLM (A10G)
□ Скачать Qwen2.5-7B через HF_TOKEN
□ Запустить infinity-embedding на том же Pod
□ Обновить env-переменные в ECS task definition
□ Smoke test: 10 запросов, убедиться в корректных ответах
□ Нагрузочный тест (locust): 300 concurrent пользователей
□ Убедиться p95 latency < 30 сек
□ Отключить OpenAI billing
```

### Стадия 2 → 3 (переход на AWS reserved)

```
□ Оформить EC2 g5.xlarge Reserved Instance (1yr)
□ Перенести vLLM + infinity с RunPod на EC2
□ Перенести Qdrant на выделенный EC2 (t3.large reserved)
□ Оформить RDS + ElastiCache Reserved Instances
□ Обновить OPENAI_BASE_URL на internal AWS endpoint
□ Настроить VPC Security Groups (только internal трафик к GPU)
□ Нагрузочный тест после миграции
□ Отключить RunPod Pod
```

---

## Рекомендованный путь

```
Сейчас (локально)     Месяц 1–6           Месяц 6+
Docker Compose    →   OpenAI/Gemini API →  vLLM self-hosted
Ollama qwen3:1.7b     ~$571–868/мес        ~$551/мес
```

1. **Старт** — Gemini 2.0 Flash API: самый дешёвый облачный вариант, данных в коде менять не нужно
2. **При росте** — RunPod vLLM с Qwen2.5-7B: сразу дешевле API и данные не уходят в OpenAI
3. **При стабильной нагрузке** — AWS g5.xlarge reserved: тот же vLLM, но с 99.9% AWS SLA
