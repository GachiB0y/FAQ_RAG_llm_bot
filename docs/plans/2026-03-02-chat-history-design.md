# Chat History Persistence — Design

**Дата:** 2026-03-02
**Статус:** Утверждён

---

## Проблема

При выходе из вкладки чата история диалога теряется — сообщения хранятся только в локальном React state и Redis (TTL 24ч). Нет персистентного хранения на уровне БД.

---

## Требования

- История хранится в PostgreSQL, привязана к `user_id`
- Каждый пользователь видит только свою историю
- Срок хранения: 90 дней (настраивается через конфиг)
- Загрузка: последние 50 сообщений, infinite scroll вверх (limit/offset)
- UX: один непрерывный поток (нет кнопки "Новый чат" сейчас)
- Архитектура: совместима с будущим вариантом C (несколько диалогов на пользователя)

---

## Архитектура

### DB Schema

```
conversations
─────────────────────────────────────────
id          UUID  PK
user_id     UUID  FK → users.id  (indexed)
created_at  timestamp
updated_at  timestamp  ← обновляется при каждом новом сообщении

messages
─────────────────────────────────────────
id               UUID  PK
conversation_id  UUID  FK → conversations.id  (CASCADE DELETE, indexed)
role             VARCHAR  ('user' | 'assistant')
content          TEXT
created_at       timestamp  (indexed for ORDER BY + range queries)
```

### Роль Redis (без изменений)

Redis остаётся как горячий кэш для RAG контекста (последние 10 сообщений для LLM). PostgreSQL — для долгосрочного хранения и пагинации.

### Поток `POST /api/v1/chat`

```
1. Найти или создать conversation для user_id
2. INSERT messages (role='user', content=message)
3. Вызвать RAG engine (Redis контекст — без изменений)
4. INSERT messages (role='assistant', content=answer)
5. UPDATE conversations.updated_at = now()
```

### Поток `GET /api/v1/chat/history`

```
1. Получить user_id из JWT токена
2. Найти conversation по user_id
3. SELECT messages WHERE conversation_id
   ORDER BY created_at DESC LIMIT ? OFFSET ?
4. Вернуть messages в хронологическом порядке (перевернуть)
```

---

## API

### `POST /api/v1/chat` — без изменений в интерфейсе

Добавляем персистентность внутри. Интерфейс запроса/ответа не меняется.

### `GET /api/v1/chat/history` — переделываем

```
GET /api/v1/chat/history?limit=50&offset=0
Authorization: Bearer <token>

Response:
{
  "messages": [
    { "role": "user",      "content": "...", "created_at": "2026-03-01T10:00:00Z" },
    { "role": "assistant", "content": "...", "created_at": "2026-03-01T10:00:05Z" }
  ],
  "total": 143,
  "limit": 50,
  "offset": 0,
  "has_more": true
}
```

Убираем параметр `session_id` — история привязана к `user_id` из токена.

### `DELETE /api/v1/chat/history` — новый

```
DELETE /api/v1/chat/history
Authorization: Bearer <token>

Response: { "deleted_count": 143 }
```

Удаляет все сообщения пользователя (conversation остаётся для будущего использования).

---

## Конфигурация

```python
# config.py — новые поля
CHAT_HISTORY_RETENTION_DAYS: int = 90   # срок хранения сообщений
CHAT_HISTORY_PAGE_SIZE: int = 50        # сообщений за один запрос
```

### Автоочистка

`arq` background job `cleanup_old_messages`, запускается раз в сутки:

```python
DELETE FROM messages
WHERE created_at < now() - INTERVAL '{retention_days} days'
```

Конфигурируется через `CHAT_HISTORY_RETENTION_DAYS` в `.env`.

---

## Frontend

### Изменяемые файлы

| Файл | Изменение |
|------|-----------|
| `features/chat/ui/ChatWidget.tsx` | загрузка истории при маунте + infinite scroll вверх |
| `features/chat/model/hooks.ts` | новый `useChatHistory` с `useInfiniteQuery` |
| `shared/api/endpoints.ts` | обновить `getHistory` (убрать session_id, добавить limit/offset) |
| `shared/api/types.ts` | обновить `ChatHistoryResponse`, добавить `created_at` в `ChatMessage` |

### Поведение infinite scroll

```
Маунт компонента → GET /history?limit=50&offset=0
Скролл вверх до предела + has_more=true → GET /history?limit=50&offset=50
Prepend старых сообщений (позиция скролла сохраняется)
```

### Новый хук

```typescript
export const useChatHistory = () => {
  return useInfiniteQuery({
    queryKey: ['chat', 'history'],
    queryFn: ({ pageParam = 0 }) =>
      chatApi.getHistory({ limit: 50, offset: pageParam }),
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? lastPage.offset + lastPage.limit : undefined,
  })
}
```

---

## Изменяемые файлы (backend)

| Файл | Изменение |
|------|-----------|
| `backend/app/models/conversation.py` | новая модель Conversation |
| `backend/app/models/message.py` | новая модель Message |
| `backend/app/models/__init__.py` | экспорт новых моделей |
| `backend/app/schemas/chat.py` | обновить ChatHistoryResponse, добавить пагинацию |
| `backend/app/api/v1/chat.py` | персистентность в POST, пагинация в GET, новый DELETE |
| `backend/app/config.py` | новые поля retention_days, page_size |
| `backend/app/worker.py` | новый arq job cleanup_old_messages |
| `backend/alembic/versions/002_chat_history.py` | миграция новых таблиц |

---

## Что не меняется

- Redis SessionManager — остаётся для RAG контекста
- RAG engine — без изменений
- JWT авторизация — без изменений
- Все остальные API эндпоинты — без изменений
- Никаких новых зависимостей

---

## Будущий апгрейд до варианта C (несколько диалогов)

Схема уже готова: `conversations` таблица поддерживает несколько записей на одного пользователя. Для апгрейда нужно будет:
1. Добавить `title` поле в `conversations`
2. Добавить `GET /api/v1/chat/conversations` (список диалогов)
3. Добавить `POST /api/v1/chat/conversations` (создать новый диалог)
4. Добавить сайдбар в frontend

Изменений в существующей схеме — **ноль**.
