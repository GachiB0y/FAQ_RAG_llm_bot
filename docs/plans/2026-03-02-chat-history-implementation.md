# Chat History Persistence — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Сохранять историю чата каждого пользователя в PostgreSQL с пагинацией (limit/offset) и автоочисткой через конфигурируемый срок хранения.

**Architecture:** Добавляем две таблицы — `conversations` (одна на пользователя) и `messages` (все сообщения). Redis остаётся для горячего RAG-контекста (10 сообщений). `GET /api/v1/chat/history` переключается с Redis на PostgreSQL + пагинация. Frontend загружает историю при маунте и подгружает старые сообщения при скролле к началу (infinite scroll вверх).

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, PostgreSQL, React, TanStack Query v5 `useInfiniteQuery`, Chakra UI

---

### Task 1: DB модели Conversation и Message

**Files:**
- Create: `backend/app/models/conversation.py`
- Create: `backend/app/models/message.py`
- Modify: `backend/app/models/__init__.py`

**Контекст:** Проект использует `UUIDMixin` и `TimestampMixin` из `backend/app/models/base.py`. Все модели наследуют от `Base` (DeclarativeBase). UUID хранятся как строки (`UUID(as_uuid=False)`).

**Step 1: Создать `backend/app/models/conversation.py`**

```python
from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin


class Conversation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "conversations"

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id"), nullable=False, index=True
    )

    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )
```

**Step 2: Создать `backend/app/models/message.py`**

```python
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin
from sqlalchemy import DateTime, func
from datetime import datetime


class Message(Base, UUIDMixin):
    __tablename__ = "messages"

    conversation_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # 'user' | 'assistant'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages"
    )
```

**Step 3: Обновить `backend/app/models/__init__.py`**

Заменить файл целиком:

```python
from .base import Base
from .user import User, UserRole
from .document import Document, DocumentStatus
from .settings import SystemSettings
from .conversation import Conversation
from .message import Message

__all__ = [
    "Base",
    "User",
    "UserRole",
    "Document",
    "DocumentStatus",
    "SystemSettings",
    "Conversation",
    "Message",
]
```

**Step 4: Проверить что нет синтаксических ошибок**

```bash
docker compose exec backend python -c "from app.models import Conversation, Message; print('OK')"
```

Ожидаемый результат: `OK`

**Step 5: Commit**

```bash
git add backend/app/models/conversation.py backend/app/models/message.py backend/app/models/__init__.py
git commit -m "feat: add Conversation and Message models"
```

---

### Task 2: Alembic миграция 002_chat_history

**Files:**
- Create: `backend/alembic/versions/002_chat_history.py`

**Контекст:** Миграция 001 (`001_initial.py`) создаёт таблицы `users`, `documents`, `system_settings`. Новая миграция идёт после неё (`down_revision = '001_initial'`).

**Step 1: Создать `backend/alembic/versions/002_chat_history.py`**

```python
"""Add chat history tables

Revision ID: 002_chat_history
Revises: 001_initial
Create Date: 2026-03-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '002_chat_history'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'conversations',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=False),
                  sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        'messages',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=False),
                  sa.ForeignKey('conversations.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table('messages')
    op.drop_table('conversations')
```

**Step 2: Применить миграцию**

```bash
docker compose exec backend alembic upgrade head
```

Ожидаемый результат:
```
INFO  [alembic.runtime.migration] Running upgrade 001_initial -> 002_chat_history, Add chat history tables
```

**Step 3: Проверить что таблицы созданы**

```bash
docker compose exec postgres psql -U faq_user -d faq_bot -c "\dt"
```

Ожидаемый результат: в списке есть `conversations` и `messages`.

**Step 4: Commit**

```bash
git add backend/alembic/versions/002_chat_history.py
git commit -m "feat: add migration 002 for chat history tables"
```

---

### Task 3: Config — добавить retention и page_size

**Files:**
- Modify: `backend/app/config.py`
- Modify: `.env.example` (если есть, иначе создать)

**Контекст:** `Settings` в `backend/app/config.py` использует `pydantic_settings.BaseSettings`. Текущий последний раздел — Upload.

**Step 1: Добавить поля в `backend/app/config.py`**

После блока `# Upload` добавить блок `# Chat`:

```python
    # Chat
    CHAT_HISTORY_RETENTION_DAYS: int = 90
    CHAT_HISTORY_PAGE_SIZE: int = 50
```

Итоговый файл `backend/app/config.py`:

```python
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal, Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    REDIS_URL: str
    QDRANT_URL: str

    # JWT
    JWT_SECRET: str
    JWT_EXPIRE_MINUTES: int = 60

    # LLM
    LLM_PROVIDER: Literal["openai", "anthropic", "ollama"] = "openai"
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3:1.7b"

    # Embeddings
    EMBEDDING_PROVIDER: Literal["openai", "ollama"] = "openai"
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # RAG
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50
    SIMILARITY_THRESHOLD: float = 0.7
    TOP_K_RESULTS: int = 5

    # Upload
    UPLOAD_DIR: str = "/app/uploads"
    MAX_FILE_SIZE_MB: int = 50

    # Chat
    CHAT_HISTORY_RETENTION_DAYS: int = 90
    CHAT_HISTORY_PAGE_SIZE: int = 50

    model_config = SettingsConfigDict(env_file=".env")


def get_settings() -> Settings:
    return Settings()
```

**Step 2: Проверить что настройки читаются**

```bash
docker compose exec backend python -c "from app.config import get_settings; s = get_settings(); print(s.CHAT_HISTORY_RETENTION_DAYS, s.CHAT_HISTORY_PAGE_SIZE)"
```

Ожидаемый результат: `90 50`

**Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "feat: add CHAT_HISTORY_RETENTION_DAYS and CHAT_HISTORY_PAGE_SIZE to config"
```

---

### Task 4: Схемы — обновить ChatHistoryResponse

**Files:**
- Modify: `backend/app/schemas/chat.py`

**Контекст:** Текущий `ChatHistoryResponse` имеет `session_id` и `messages: list[ChatHistoryMessage]`. Новый вариант — с пагинацией. `ChatHistoryMessage` переименовываем в `ChatHistoryItem` и добавляем `created_at`.

**Step 1: Заменить содержимое `backend/app/schemas/chat.py`**

```python
from datetime import datetime
from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


class ChatSource(BaseModel):
    document: str
    page: int | None
    chunk: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
    confidence: float
    session_id: str


class ChatHistoryItem(BaseModel):
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatHistoryResponse(BaseModel):
    messages: list[ChatHistoryItem]
    total: int
    limit: int
    offset: int
    has_more: bool


class DeleteHistoryResponse(BaseModel):
    deleted_count: int
```

**Step 2: Проверить что схемы импортируются**

```bash
docker compose exec backend python -c "from app.schemas.chat import ChatHistoryResponse, ChatHistoryItem; print('OK')"
```

Ожидаемый результат: `OK`

**Step 3: Commit**

```bash
git add backend/app/schemas/chat.py
git commit -m "feat: update ChatHistoryResponse schema with pagination"
```

---

### Task 5: Сервис истории чата

**Files:**
- Create: `backend/app/services/__init__.py` (пустой, если нет)
- Create: `backend/app/services/chat_history.py`

**Контекст:** Новый сервисный слой. Функции принимают `AsyncSession` из SQLAlchemy. Модели `Conversation` и `Message` импортируем из `app.models`. `Message.created_at` — индексированное поле для быстрых выборок.

**Step 1: Создать `backend/app/services/__init__.py`** (пустой файл)

```python
```

**Step 2: Создать `backend/app/services/chat_history.py`**

```python
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Message


async def get_or_create_conversation(user_id: str, db: AsyncSession) -> Conversation:
    """Get existing conversation for user or create a new one."""
    result = await db.execute(
        select(Conversation).where(Conversation.user_id == user_id)
    )
    conversation = result.scalar_one_or_none()

    if conversation is None:
        conversation = Conversation(id=str(uuid4()), user_id=user_id)
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)

    return conversation


async def save_message(
    conversation_id: str, role: str, content: str, db: AsyncSession
) -> Message:
    """Save a single message to the conversation."""
    message = Message(
        id=str(uuid4()),
        conversation_id=conversation_id,
        role=role,
        content=content,
    )
    db.add(message)

    # Update conversation updated_at
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if conversation:
        conversation.updated_at = datetime.now(timezone.utc)

    await db.commit()
    return message


async def get_history(
    user_id: str, limit: int, offset: int, db: AsyncSession
) -> tuple[list[Message], int]:
    """
    Get paginated chat history for user.
    Returns (messages_in_asc_order, total_count).
    Messages are returned in chronological order (oldest first).
    Pagination works from the END: offset=0 → most recent `limit` messages.
    """
    result = await db.execute(
        select(Conversation).where(Conversation.user_id == user_id)
    )
    conversation = result.scalar_one_or_none()

    if conversation is None:
        return [], 0

    # Count total messages
    count_result = await db.execute(
        select(func.count(Message.id)).where(
            Message.conversation_id == conversation.id
        )
    )
    total = count_result.scalar_one()

    if total == 0:
        return [], 0

    # Get messages: newest first (for offset), then reverse for chronological display
    messages_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    messages = list(messages_result.scalars().all())
    messages.reverse()  # chronological order for display

    return messages, total


async def delete_history(user_id: str, db: AsyncSession) -> int:
    """Delete all messages for user. Returns count of deleted messages."""
    result = await db.execute(
        select(Conversation).where(Conversation.user_id == user_id)
    )
    conversation = result.scalar_one_or_none()

    if conversation is None:
        return 0

    count_result = await db.execute(
        select(func.count(Message.id)).where(
            Message.conversation_id == conversation.id
        )
    )
    count = count_result.scalar_one()

    await db.execute(
        delete(Message).where(Message.conversation_id == conversation.id)
    )
    await db.commit()

    return count


async def cleanup_old_messages(retention_days: int, db: AsyncSession) -> int:
    """Delete messages older than retention_days. Returns count of deleted messages."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    count_result = await db.execute(
        select(func.count(Message.id)).where(Message.created_at < cutoff)
    )
    count = count_result.scalar_one()

    await db.execute(
        delete(Message).where(Message.created_at < cutoff)
    )
    await db.commit()

    return count
```

**Step 3: Проверить что сервис импортируется**

```bash
docker compose exec backend python -c "from app.services.chat_history import get_or_create_conversation; print('OK')"
```

Ожидаемый результат: `OK`

**Step 4: Commit**

```bash
git add backend/app/services/__init__.py backend/app/services/chat_history.py
git commit -m "feat: add chat history service with CRUD and cleanup"
```

---

### Task 6: Обновить API эндпоинты чата

**Files:**
- Modify: `backend/app/api/v1/chat.py`

**Контекст:** Текущий файл (`backend/app/api/v1/chat.py`) имеет два эндпоинта. Нужно:
1. `POST /chat` — добавить `db` dependency и сохранение в PostgreSQL
2. `GET /chat/history` — переключить с Redis на PostgreSQL + пагинация (убрать `session_id` параметр)
3. `DELETE /chat/history` — новый эндпоинт

Dependency `get_db` уже есть в `backend/app/database.py`. `AsyncSession` нужно добавить в deps.

**Step 1: Проверить как `get_db` используется в других эндпоинтах**

```bash
grep -r "get_db\|AsyncSession" /app/app/api/ 2>/dev/null
```

Запустить из docker: `docker compose exec backend grep -r "get_db" app/api/`

**Step 2: Полностью заменить `backend/app/api/v1/chat.py`**

```python
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_rag_engine,
    get_redis,
    get_session_id,
)
from app.database import get_db
from app.models.user import User
from app.core.rag import RAGEngine
from app.core.session import SessionManager
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatHistoryResponse,
    ChatHistoryItem,
    DeleteHistoryResponse,
)
from app.services.chat_history import (
    get_or_create_conversation,
    save_message,
    get_history,
    delete_history,
)
from app.config import get_settings

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    user: Annotated[User, Depends(get_current_user)],
    rag: Annotated[RAGEngine, Depends(get_rag_engine)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
    session_id: Annotated[str | None, Depends(get_session_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    session_mgr = SessionManager(redis_client)

    # Redis: manage hot context for RAG (unchanged)
    if session_id:
        session = await session_mgr.get_session(session_id)
        if not session:
            session_id = await session_mgr.create_session(user.id)
    else:
        session_id = await session_mgr.create_session(user.id)

    history = await session_mgr.get_history(session_id)

    result = rag.query(data.message, chat_history=history)

    await session_mgr.add_message(session_id, "user", data.message)
    await session_mgr.add_message(session_id, "assistant", result["answer"])

    # PostgreSQL: persist messages permanently
    conversation = await get_or_create_conversation(user.id, db)
    await save_message(conversation.id, "user", data.message, db)
    await save_message(conversation.id, "assistant", result["answer"], db)

    return ChatResponse(
        answer=result["answer"],
        sources=result["sources"],
        confidence=result["confidence"],
        session_id=session_id,
    )


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    messages, total = await get_history(user.id, limit, offset, db)

    return ChatHistoryResponse(
        messages=[
            ChatHistoryItem(
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
            )
            for msg in messages
        ],
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


@router.delete("/history", response_model=DeleteHistoryResponse)
async def clear_chat_history(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    deleted_count = await delete_history(user.id, db)
    return DeleteHistoryResponse(deleted_count=deleted_count)
```

**Step 3: Проверить что бэкенд стартует без ошибок**

```bash
docker compose restart backend
docker compose logs backend --tail=20
```

Ожидаемый результат: нет ошибок импорта, `Application startup complete`.

**Step 4: Протестировать GET /history через curl**

```bash
# Получить токен (замени на реальный после логина)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"admin123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/chat/history?limit=10&offset=0" | python3 -m json.tool
```

Ожидаемый результат:
```json
{
  "messages": [],
  "total": 0,
  "limit": 10,
  "offset": 0,
  "has_more": false
}
```

**Step 5: Commit**

```bash
git add backend/app/api/v1/chat.py
git commit -m "feat: persist chat messages to PostgreSQL, add paginated history and delete endpoints"
```

---

### Task 7: Автоочистка старых сообщений

**Files:**
- Modify: `backend/app/main.py`

**Контекст:** В `backend/app/main.py` есть `lifespan` context manager. Добавим asyncio background task, который раз в сутки вызывает `cleanup_old_messages`. Используем `AsyncSessionLocal` из `backend/app/database.py`.

**Step 1: Заменить `backend/app/main.py`**

```python
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.config import get_settings
from app.database import AsyncSessionLocal
from app.services.chat_history import cleanup_old_messages

logger = logging.getLogger(__name__)

CLEANUP_INTERVAL_SECONDS = 86400  # 24 hours


async def _cleanup_loop(retention_days: int) -> None:
    """Background task: delete messages older than retention_days every 24h."""
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        try:
            async with AsyncSessionLocal() as db:
                deleted = await cleanup_old_messages(retention_days, db)
                if deleted > 0:
                    logger.info(f"Cleanup: deleted {deleted} messages older than {retention_days} days")
        except Exception as exc:
            logger.error(f"Cleanup task error: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting FAQ RAG Bot with LLM provider: {settings.LLM_PROVIDER}")

    cleanup_task = asyncio.create_task(
        _cleanup_loop(settings.CHAT_HISTORY_RETENTION_DAYS)
    )

    yield

    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    print("Shutting down FAQ RAG Bot")


app = FastAPI(
    title="FAQ RAG Bot API",
    description="RAG-based FAQ Bot for documentation Q&A",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

**Step 2: Перезапустить бэкенд и проверить логи**

```bash
docker compose restart backend
docker compose logs backend --tail=20
```

Ожидаемый результат: `Starting FAQ RAG Bot with LLM provider: ollama`, нет ошибок.

**Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: add background cleanup task for old chat messages"
```

---

### Task 8: Frontend — типы и API клиент

**Files:**
- Modify: `frontend/src/shared/api/types.ts`
- Modify: `frontend/src/shared/api/endpoints.ts`

**Контекст:**
- `types.ts`: обновляем `ChatMessage` (добавить `created_at`) и `ChatHistoryResponse` (добавить пагинацию, убрать `session_id`)
- `endpoints.ts`: обновляем `chatApi.getHistory` — убрать `session_id`, добавить `limit`/`offset`

**Step 1: В `frontend/src/shared/api/types.ts` заменить блок Chat types**

Найти раздел `// Chat types` (строки 57-82) и заменить:

```typescript
// Chat types
export interface ChatRequest {
  message: string;
}

export interface ChatSource {
  document: string;
  page: number | null;
  chunk: string;
}

export interface ChatResponse {
  answer: string;
  sources: ChatSource[];
  confidence: number;
  session_id: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

export interface ChatHistoryResponse {
  messages: ChatMessage[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}
```

**Step 2: В `frontend/src/shared/api/endpoints.ts` заменить `chatApi`**

Найти блок `// Chat API` (строки 89-103) и заменить:

```typescript
// Chat API
export const chatApi = {
  send: async (data: ChatRequest, sessionId?: string): Promise<ChatResponse> => {
    const response = await api.post<ChatResponse>('/api/v1/chat', data, {
      headers: sessionId ? { 'X-Session-Id': sessionId } : {},
    });
    return response.data;
  },

  getHistory: async (params: {
    limit: number;
    offset: number;
  }): Promise<ChatHistoryResponse> => {
    const response = await api.get<ChatHistoryResponse>('/api/v1/chat/history', {
      params,
    });
    return response.data;
  },

  clearHistory: async (): Promise<{ deleted_count: number }> => {
    const response = await api.delete<{ deleted_count: number }>('/api/v1/chat/history');
    return response.data;
  },
};
```

**Step 3: Проверить typecheck**

```bash
cd frontend && pnpm typecheck 2>&1 | head -30
```

Ожидаемый результат: 0 ошибок типизации (или только те что были до изменений).

**Step 4: Commit**

```bash
git add frontend/src/shared/api/types.ts frontend/src/shared/api/endpoints.ts
git commit -m "feat: update ChatHistoryResponse types with pagination, add clearHistory"
```

---

### Task 9: Frontend — хук useChatHistory

**Files:**
- Modify: `frontend/src/features/chat/model/hooks.ts`

**Контекст:** Текущий `hooks.ts` содержит только `useSendMessage`. Добавляем `useChatHistory` с `useInfiniteQuery`. `useInfiniteQuery` из TanStack Query v5 принимает `initialPageParam` и `getNextPageParam`.

**Step 1: Заменить содержимое `frontend/src/features/chat/model/hooks.ts`**

```typescript
import type { ChatRequest, ChatHistoryResponse } from '@shared/api';
import { chatApi } from '@shared/api';
import { useMutation, useInfiniteQuery } from '@tanstack/react-query';

const CHAT_PAGE_SIZE = 50;

export const useSendMessage = () => {
  return useMutation({
    mutationFn: ({ data, sessionId }: { data: ChatRequest; sessionId?: string }) =>
      chatApi.send(data, sessionId),
  });
};

export const useChatHistory = () => {
  return useInfiniteQuery<ChatHistoryResponse>({
    queryKey: ['chat', 'history'],
    queryFn: ({ pageParam }) =>
      chatApi.getHistory({
        limit: CHAT_PAGE_SIZE,
        offset: pageParam as number,
      }),
    initialPageParam: 0,
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? lastPage.offset + lastPage.limit : undefined,
    staleTime: 0,
  });
};
```

**Step 2: Проверить экспорт из `features/chat/model`**

Прочитать `frontend/src/features/chat/model/index.ts` и добавить экспорт:

```typescript
export { useSendMessage, useChatHistory } from './hooks';
```

**Step 3: Проверить typecheck**

```bash
cd frontend && pnpm typecheck 2>&1 | head -30
```

Ожидаемый результат: 0 ошибок.

**Step 4: Commit**

```bash
git add frontend/src/features/chat/model/hooks.ts frontend/src/features/chat/model/index.ts
git commit -m "feat: add useChatHistory hook with infinite query pagination"
```

---

### Task 10: Frontend — ChatWidget с infinite scroll

**Files:**
- Modify: `frontend/src/features/chat/ui/ChatWidget.tsx`

**Контекст:** Текущий `ChatWidget.tsx` хранит сообщения в `useState`. Новая версия:
- При маунте загружает последние 50 сообщений через `useChatHistory`
- При скролле к самому верху (`scrollTop === 0`) загружает следующую страницу (старые сообщения)
- При загрузке следующей страницы сохраняет позицию скролла (через `scrollHeight` diff)
- `ChatMessageItem` расширяем полем `created_at` (опциональным, т.к. новые сообщения добавляются без него)

**Step 1: Полностью заменить `frontend/src/features/chat/ui/ChatWidget.tsx`**

```tsx
import { useCallback, useEffect, useRef, useState } from 'react';
import { useIntl } from 'react-intl';
import {
  Badge,
  Box,
  Button,
  Collapse,
  Flex,
  IconButton,
  Input,
  Spinner,
  Text,
  useDisclosure,
  useToast,
  VStack,
} from '@chakra-ui/react';
import { useSendMessage, useChatHistory } from '@features/chat/model';
import type { ChatSource } from '@shared/api';

interface ChatMessageItem {
  role: 'user' | 'assistant';
  content: string;
  sources?: ChatSource[];
  confidence?: number;
  created_at?: string;
}

const SourcesSection = ({ sources }: { sources: ChatSource[] }) => {
  const { formatMessage } = useIntl();
  const { isOpen, onToggle } = useDisclosure();

  return (
    <Box mt={1}>
      <Button variant="link" size="xs" onClick={onToggle} colorScheme="gray">
        {formatMessage({ id: 'chat.sources' })} ({sources.length})
      </Button>
      <Collapse in={isOpen}>
        <VStack align="start" spacing={1} mt={1} pl={2} borderLeftWidth="2px" borderColor="gray.300">
          {sources.map((source, idx) => (
            <Text key={idx} fontSize="xs" color="gray.500">
              {source.document}
              {source.page != null ? ` (p. ${source.page})` : ''}
            </Text>
          ))}
        </VStack>
      </Collapse>
    </Box>
  );
};

export const ChatWidget = () => {
  const { formatMessage } = useIntl();
  const toast = useToast();
  const [localMessages, setLocalMessages] = useState<ChatMessageItem[]>([]);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [historyLoaded, setHistoryLoaded] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const prevScrollHeightRef = useRef(0);

  const mutation = useSendMessage();
  const {
    data: historyData,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading: isHistoryLoading,
  } = useChatHistory();

  // On initial history load — populate localMessages and scroll to bottom
  useEffect(() => {
    if (!historyData || historyLoaded) return;

    const allPages = historyData.pages;
    if (allPages.length === 0) {
      setHistoryLoaded(true);
      return;
    }

    // Pages: page[0] = most recent messages (offset=0), page[1] = older, etc.
    // Each page is already in chronological order (reversed in service layer).
    // We need: oldest first → page[N-1] first, page[0] last
    const historicMessages: ChatMessageItem[] = allPages
      .slice()
      .reverse()
      .flatMap((page) =>
        page.messages.map((msg) => ({
          role: msg.role as 'user' | 'assistant',
          content: msg.content,
          created_at: msg.created_at,
        }))
      );

    setLocalMessages(historicMessages);
    setHistoryLoaded(true);
  }, [historyData, historyLoaded]);

  // After history loads — scroll to bottom once
  useEffect(() => {
    if (historyLoaded && !isFetchingNextPage) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'auto' });
    }
  }, [historyLoaded]);

  // After loading older page — restore scroll position
  useEffect(() => {
    if (!isFetchingNextPage && historyData && historyData.pages.length > 1) {
      const allPages = historyData.pages;
      const historicMessages: ChatMessageItem[] = allPages
        .slice()
        .reverse()
        .flatMap((page) =>
          page.messages.map((msg) => ({
            role: msg.role as 'user' | 'assistant',
            content: msg.content,
            created_at: msg.created_at,
          }))
        );
      setLocalMessages(historicMessages);

      // Restore scroll position
      if (scrollAreaRef.current) {
        const newScrollHeight = scrollAreaRef.current.scrollHeight;
        scrollAreaRef.current.scrollTop = newScrollHeight - prevScrollHeightRef.current;
      }
    }
  }, [historyData?.pages.length, isFetchingNextPage]);

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    if (historyLoaded) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [localMessages.length, historyLoaded]);

  // Infinite scroll: load older messages when user scrolls to top
  const handleScroll = useCallback(
    (e: React.UIEvent<HTMLDivElement>) => {
      const el = e.currentTarget;
      if (el.scrollTop === 0 && hasNextPage && !isFetchingNextPage) {
        prevScrollHeightRef.current = el.scrollHeight;
        fetchNextPage();
      }
    },
    [hasNextPage, isFetchingNextPage, fetchNextPage],
  );

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || mutation.isPending) return;

    const userMessage: ChatMessageItem = { role: 'user', content: trimmed };
    setLocalMessages((prev) => [...prev, userMessage]);
    setInput('');

    mutation.mutate(
      { data: { message: trimmed }, sessionId },
      {
        onSuccess: (response) => {
          setSessionId(response.session_id);
          const assistantMessage: ChatMessageItem = {
            role: 'assistant',
            content: response.answer,
            sources: response.sources,
            confidence: response.confidence,
          };
          setLocalMessages((prev) => [...prev, assistantMessage]);
        },
        onError: () => {
          toast({
            title: formatMessage({ id: 'chat.error' }),
            status: 'error',
            duration: 3000,
            isClosable: true,
          });
        },
      },
    );
  }, [input, mutation, sessionId, toast, formatMessage]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const isEmpty = localMessages.length === 0 && !isHistoryLoading;

  return (
    <Flex direction="column" h="70vh" borderWidth="1px" borderRadius="lg" overflow="hidden">
      <Box flex="1" overflowY="auto" p={4} ref={scrollAreaRef} onScroll={handleScroll}>
        {isFetchingNextPage && (
          <Flex justify="center" py={2}>
            <Spinner size="sm" />
          </Flex>
        )}
        {isHistoryLoading && (
          <Flex justify="center" align="center" h="full">
            <Spinner />
          </Flex>
        )}
        {isEmpty && (
          <Flex justify="center" align="center" h="full">
            <Text color="gray.500">{formatMessage({ id: 'chat.empty' })}</Text>
          </Flex>
        )}
        <VStack spacing={3} align="stretch">
          {localMessages.map((msg, idx) => (
            <Flex key={idx} justify={msg.role === 'user' ? 'flex-end' : 'flex-start'}>
              <Box
                maxW="75%"
                px={4}
                py={2}
                borderRadius="lg"
                bg={msg.role === 'user' ? 'blue.500' : 'gray.100'}
                color={msg.role === 'user' ? 'white' : 'inherit'}
              >
                <Text whiteSpace="pre-wrap">{msg.content}</Text>
                {msg.role === 'assistant' && msg.confidence != null && (
                  <Badge mt={1} colorScheme="green" fontSize="xs">
                    {formatMessage({ id: 'chat.confidence' })}: {Math.round(msg.confidence * 100)}%
                  </Badge>
                )}
                {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
                  <SourcesSection sources={msg.sources} />
                )}
              </Box>
            </Flex>
          ))}
          {mutation.isPending && (
            <Flex justify="flex-start">
              <Box px={4} py={2} borderRadius="lg" bg="gray.100">
                <Spinner size="sm" />
              </Box>
            </Flex>
          )}
          <Box ref={messagesEndRef} />
        </VStack>
      </Box>

      <Flex p={3} borderTopWidth="1px" gap={2}>
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={formatMessage({ id: 'chat.placeholder' })}
          isDisabled={mutation.isPending}
        />
        <IconButton
          aria-label={formatMessage({ id: 'chat.send' })}
          onClick={handleSend}
          isLoading={mutation.isPending}
          colorScheme="blue"
        >
          {'\u2192'}
        </IconButton>
      </Flex>
    </Flex>
  );
};
```

**Примечание:** Кнопка "Новый чат" убрана согласно дизайну (вариант A). Заголовок панели убран тоже.

**Step 2: Проверить lint**

```bash
cd frontend && pnpm lint 2>&1 | head -40
```

Исправить все ошибки линтера.

**Step 3: Проверить typecheck**

```bash
cd frontend && pnpm typecheck 2>&1 | head -40
```

Ожидаемый результат: 0 ошибок.

**Step 4: Commit**

```bash
git add frontend/src/features/chat/ui/ChatWidget.tsx
git commit -m "feat: load chat history on mount with infinite scroll pagination"
```

---

### Task 11: Сборка и ручное тестирование

**Step 1: Пересобрать frontend**

```bash
cd /Users/admin/Documents/project/FAQ_RAG_llm_bot
docker compose build frontend
```

Ожидаемый результат: `Image faq_rag_llm_bot-frontend Built`

**Step 2: Перезапустить контейнеры**

```bash
docker compose up -d frontend backend
```

**Step 3: Проверить HTTP статус**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000
```

Ожидаемый результат: `200`

**Step 4: Тест 1 — История сохраняется**

1. Открыть `http://localhost:3000/login`, залогиниться
2. Открыть `/admin/chat`, написать 2-3 сообщения
3. Закрыть вкладку / обновить страницу (F5)
4. ✅ Ожидаемо: сообщения снова отображаются

**Step 5: Тест 2 — API возвращает историю**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"admin123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/chat/history?limit=10&offset=0" | python3 -m json.tool
```

Ожидаемый результат: JSON с `messages`, `total > 0`, `has_more`.

**Step 6: Тест 3 — Пагинация**

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/chat/history?limit=2&offset=0" | python3 -m json.tool
```

Ожидаемый результат: ровно 2 сообщения, `has_more: true` (если всего > 2).

**Step 7: Тест 4 — DELETE**

```bash
curl -s -X DELETE -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/chat/history" | python3 -m json.tool
```

Ожидаемый результат: `{ "deleted_count": N }` где N > 0.

---

### Контрольный список перед финишем

```
□ conversations и messages таблицы созданы в БД
□ POST /chat сохраняет в PostgreSQL
□ GET /chat/history возвращает пагинированный ответ (без session_id параметра)
□ DELETE /chat/history удаляет сообщения
□ CHAT_HISTORY_RETENTION_DAYS читается из конфига
□ Cleanup background task стартует вместе с приложением
□ Frontend: история загружается при маунте
□ Frontend: бесконечная прокрутка вверх подгружает старые сообщения
□ pnpm lint — без ошибок
□ pnpm typecheck — без ошибок
□ docker compose build frontend — без ошибок
□ Тест 1 (история сохраняется после обновления страницы) — ✅
□ Тест 2 (API возвращает историю) — ✅
□ Тест 3 (пагинация) — ✅
□ Тест 4 (DELETE) — ✅
```
