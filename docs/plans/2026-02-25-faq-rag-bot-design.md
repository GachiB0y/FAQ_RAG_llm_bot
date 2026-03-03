# FAQ RAG Bot — Дизайн-документ

**Дата:** 2026-02-25
**Статус:** Утверждён

## Обзор

RAG-бот для ответов на вопросы по документации. Каждая компания получает изолированный инстанс. Бот не галлюцинирует — если ответа нет в документах, честно говорит "не знаю".

## Требования

| Аспект | Решение |
|--------|---------|
| Тип | RAG-бот по документации |
| Критично | Не галлюцинировать, цитировать источники |
| Мультитенантность | Один инстанс = одна компания |
| API | REST (с возможностью добавить Telegram/Slack) |
| Админка | React SPA (по шаблону заказчика) |
| LLM | Абстракция (OpenAI/Claude/локальные) |
| Векторная БД | Qdrant |
| Бэкенд | Python + FastAPI |
| Аутентификация | JWT |
| Документы | TXT, MD, HTML, PDF, DOCX, XLSX |
| Деплой | Docker |
| История | Сессионная память диалогов |

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                      Docker Compose                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                    FastAPI Backend                  │   │
│   ├─────────────────────────────────────────────────────┤   │
│   │  ┌───────────┐  ┌───────────┐  ┌─────────────────┐  │   │
│   │  │  REST API │  │   Auth    │  │  Admin API      │  │   │
│   │  │  /chat    │  │   JWT     │  │  /documents     │  │   │
│   │  └─────┬─────┘  └───────────┘  └────────┬────────┘  │   │
│   │        │                                │           │   │
│   │        ▼                                ▼           │   │
│   │  ┌─────────────────────────────────────────────┐    │   │
│   │  │              RAG Core (LlamaIndex)          │    │   │
│   │  │  ┌──────────┐ ┌──────────┐ ┌─────────────┐  │    │   │
│   │  │  │ Retriever│ │ LLM      │ │ Doc Loader  │  │    │   │
│   │  │  │          │ │ Adapter  │ │ & Chunker   │  │    │   │
│   │  │  └──────────┘ └──────────┘ └─────────────┘  │    │   │
│   │  └─────────────────────────────────────────────┘    │   │
│   └─────────────────────────────────────────────────────┘   │
│                              │                              │
│          ┌───────────────────┼───────────────────┐          │
│          ▼                   ▼                   ▼          │
│   ┌─────────────┐     ┌─────────────┐     ┌───────────┐     │
│   │   Qdrant    │     │  PostgreSQL │     │   Redis   │     │
│   │  (vectors)  │     │  (users,    │     │ (sessions)│     │
│   │             │     │   metadata) │     │           │     │
│   └─────────────┘     └─────────────┘     └───────────┘     │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    React Admin SPA                          │
│   (структура по шаблону заказчика)                          │
└─────────────────────────────────────────────────────────────┘
```

## REST API

### Chat API (публичный)

```
POST /api/v1/chat
Headers:
  Authorization: Bearer <jwt_token>
  X-Session-ID: <uuid>

Request:
{
  "message": "Почему мне начислили 5 очков за этот выстрел?"
}

Response:
{
  "answer": "Согласно правилам IPSC, попадание в зону A мишени даёт 5 очков...",
  "sources": [
    {
      "document": "IPSC_Rules_2024.pdf",
      "page": 42,
      "chunk": "Зона A — 5 очков, зона C — 3 очка..."
    }
  ],
  "confidence": 0.89,
  "session_id": "uuid"
}

GET /api/v1/chat/history?session_id=<uuid>
```

### Admin API

```
# Документы
POST   /api/v1/admin/documents
GET    /api/v1/admin/documents
GET    /api/v1/admin/documents/{id}
DELETE /api/v1/admin/documents/{id}

# Пользователи
POST   /api/v1/admin/users
GET    /api/v1/admin/users
PUT    /api/v1/admin/users/{id}
DELETE /api/v1/admin/users/{id}

# Настройки
GET    /api/v1/admin/settings
PUT    /api/v1/admin/settings

# Аутентификация
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout
```

## Структура проекта

```
faq-rag-bot/
├── docker-compose.yml
├── .env.example
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic/
│   │
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   │
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── chat.py
│   │   │   │   ├── documents.py
│   │   │   │   ├── users.py
│   │   │   │   ├── settings.py
│   │   │   │   └── auth.py
│   │   │   └── deps.py
│   │   │
│   │   ├── core/
│   │   │   ├── rag/
│   │   │   │   ├── engine.py
│   │   │   │   ├── loader.py
│   │   │   │   ├── chunker.py
│   │   │   │   └── retriever.py
│   │   │   │
│   │   │   ├── llm/
│   │   │   │   ├── base.py
│   │   │   │   ├── openai.py
│   │   │   │   ├── anthropic.py
│   │   │   │   └── ollama.py
│   │   │   │
│   │   │   └── session.py
│   │   │
│   │   ├── models/
│   │   ├── schemas/
│   │   └── services/
│   │
│   └── tests/
│
├── frontend/                # По шаблону заказчика
│
└── docs/
    └── plans/
```

## RAG-пайплайн

### Загрузка документов

```
Файл → Doc Loader → Chunker → Embeddings → Qdrant
```

- Chunk size: 512-1024 токенов
- Overlap: 50-100 токенов
- Embeddings: OpenAI или локальная модель

### Ответ на вопрос

```
Вопрос + История → Embeddings → Retriever (top-K) → Confidence Check → LLM → Ответ + источники
```

### Защита от галлюцинаций

| Механизм | Как работает |
|----------|--------------|
| Confidence threshold | Если similarity < 0.7 — не отвечаем |
| Строгий промпт | LLM запрещено выдумывать |
| Цитирование | Каждый ответ содержит ссылки на источники |
| Ограничение контекста | LLM видит только найденные чанки |

## Хранение данных

### PostgreSQL

```sql
users
├── id, email, password_hash, role, created_at, updated_at

documents
├── id, filename, original_name, file_type, file_size
├── chunk_count, status, uploaded_by, created_at, updated_at

settings
├── id, key, value (JSONB), updated_at
```

### Redis

```
session:{session_id} → messages[], TTL 24h
cache:{question_hash} → answer + sources, TTL 1h
```

### Qdrant

```
Collection: documents
Vector: 1536 dim (OpenAI) или 384 (local)
Payload: document_id, filename, page, chunk_index, text
```

## Docker

```yaml
services:
  backend:    # FastAPI, port 8000
  frontend:   # React, port 3000
  postgres:   # PostgreSQL 16
  redis:      # Redis 7
  qdrant:     # Qdrant latest
```

## Переменные окружения

```bash
LLM_PROVIDER=openai|anthropic|ollama
EMBEDDING_PROVIDER=openai|local
CHUNK_SIZE=512
SIMILARITY_THRESHOLD=0.7
TOP_K_RESULTS=5
JWT_SECRET=...
DATABASE_URL=...
REDIS_URL=...
QDRANT_URL=...
```

## Границы MVP

### Входит

- REST API для чата с историей сессий
- Загрузка документов (PDF, DOCX, TXT, MD, HTML, XLSX)
- Админ-панель (React)
- JWT аутентификация
- Выбор LLM провайдера
- Docker-деплой

### Не входит (на потом)

- Telegram/Slack боты
- Аналитика
- Мультиязычность
- Fine-tuning
- Rate limiting
